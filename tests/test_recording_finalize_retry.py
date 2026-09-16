import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from daw_runtime import RecordingSpool


class RecordingFinalizeRetryTests(unittest.TestCase):
    def test_sync_and_publish_failures_preserve_previous_take_and_allow_retry(self):
        for operation in ("fsync", "publish"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as raw:
                root=Path(raw); target=root/"take.wav";target.write_bytes(b"previous")
                spool=RecordingSpool(root);spool.begin("retry",acknowledge_physical_input=True)
                spool.append_s32(struct.pack("<ii",123,-123),1)
                try:
                    target.unlink()
                    context=patch("daw_runtime.os.fsync",side_effect=OSError("injected failure")) if operation=="fsync" else patch("daw_runtime.publish_hardlink",side_effect=OSError("injected failure"))
                    with context:
                        with self.assertRaises(OSError):spool.finish("take.wav")
                    self.assertFalse(target.exists());self.assertTrue(spool._temp.exists())
                    with self.assertRaises(RuntimeError):spool.begin("replacement",acknowledge_physical_input=True)
                    receipt=spool.finish("take.wav")
                    self.assertEqual(receipt["frames"],1);self.assertTrue(receipt["directoryDurable"]);self.assertFalse(receipt["partialCleanupPending"])
                    with wave.open(str(target),"rb") as output:self.assertEqual(output.readframes(1),struct.pack("<ii",123,-123))
                finally:spool.abort()

    def test_parent_directory_sync_failure_rolls_back_publication_for_retry(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);spool=RecordingSpool(root);spool.begin("dirsync",acknowledge_physical_input=True);spool.append_s32(struct.pack("<ii",1,-1),1)
            try:
                with patch("durable_filesystem.fsync_directory",side_effect=OSError("directory sync failed")):
                    with self.assertRaisesRegex(OSError,"directory sync failed"):spool.finish("take.wav")
                self.assertFalse((root/"take.wav").exists());self.assertTrue(spool._temp.exists())
                receipt=spool.finish("take.wav");self.assertTrue(receipt["directoryDurable"]);self.assertFalse(receipt["partialCleanupPending"])
            finally:spool.abort()

    def test_cleanup_directory_sync_failure_reports_pending_after_durable_publication(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);spool=RecordingSpool(root);spool.begin("cleanup-sync",acknowledge_physical_input=True);spool.append_s32(struct.pack("<ii",1,-1),1)
            import durable_filesystem
            real=durable_filesystem.fsync_directory;calls=0
            def sync(path):
                nonlocal calls;calls+=1
                if calls==2:raise OSError("cleanup directory sync failed")
                return real(path)
            with patch("durable_filesystem.fsync_directory",side_effect=sync):receipt=spool.finish("take.wav")
            self.assertTrue((root/"take.wav").exists());self.assertTrue(receipt["directoryDurable"]);self.assertTrue(receipt["partialCleanupPending"])

    def test_header_failure_cannot_be_retried_as_success(self):
        with tempfile.TemporaryDirectory() as raw:
            spool=RecordingSpool(Path(raw));spool.begin("header",acknowledge_physical_input=True)
            try:
                with patch.object(spool._wave,"close",side_effect=OSError("header write failed")):
                    with self.assertRaises(OSError):spool.finish("take.wav")
                with self.assertRaisesRegex(RuntimeError,"header finalization failed"):spool.finish("take.wav")
                self.assertFalse((Path(raw)/"take.wav").exists())
            finally:spool.abort()
