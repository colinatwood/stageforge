import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from recording_recovery import recover_partial
from daw_capture import CaptureDrainer


class RecordingRecoveryTests(unittest.TestCase):
    def test_panel_workflow(self):
        subprocess.run(["node", str(Path(__file__).with_name("recovery_panel_test.js"))], check=True)

    def test_candidate_listing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / ".one.partial.wav").write_bytes(b"partial")
            (root / "finished.wav").write_bytes(b"done")
            (root / ".link.partial.wav").symlink_to(root / ".one.partial.wav")
            capture = CaptureDrainer(None, root)
            self.assertEqual(capture.recovery_candidates()["files"], [{"fileName": ".one.partial.wav", "bytes": 7}])
            capture.spool = object()
            self.assertFalse(capture.recovery_candidates()["available"])
            self.assertEqual(capture.recovery_candidates()["files"], [])

    def test_stale_header_recovers_complete_frames_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); source = root / ".take.partial.wav"
            with wave.open(str(source), "wb") as output:
                output.setnchannels(2); output.setsampwidth(4); output.setframerate(192000)
                output.writeframes(struct.pack("<ii", 123, -123))
            with source.open("ab") as output:
                output.write(struct.pack("<ii", 456, -456) + b"cut")
            before = source.read_bytes()
            receipt = recover_partial(root, source.name)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(receipt["frames"], 2)
            self.assertEqual(receipt["discardedTrailingBytes"], 3)
            self.assertFalse(receipt["continuityVerified"]);self.assertTrue(receipt["directoryDurable"]);self.assertFalse(receipt["temporaryCleanupPending"])
            with wave.open(receipt["path"], "rb") as result:
                self.assertEqual(result.getnframes(), 2)
                self.assertEqual(result.readframes(2), before[44:60])
            again = recover_partial(root, source.name)
            self.assertNotEqual(receipt["path"], again["path"])
            self.assertEqual(list(root.glob(".recovery-*")), [])


    def test_directory_sync_failure_rolls_back_recovered_publication(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);source=root/".take.partial.wav"
            with wave.open(str(source),"wb") as output:
                output.setnchannels(2);output.setsampwidth(4);output.setframerate(192000);output.writeframes(struct.pack("<ii",1,-1))
            with patch("durable_filesystem.fsync_directory",side_effect=OSError("directory sync failed")):
                with self.assertRaisesRegex(OSError,"directory sync failed"):recover_partial(root,source.name)
            self.assertEqual(list(root.glob("recovered-*")),[]);self.assertTrue(source.exists())

    def test_rejects_escape_symlink_and_invalid_header(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); source = root / ".bad.partial.wav"
            source.write_bytes(b"invalid")
            (root / ".link.partial.wav").symlink_to(source)
            for name in ("../bad.partial.wav", ".bad.partial.wav", ".link.partial.wav"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    recover_partial(root, name)
            self.assertEqual(list(root.glob("recovered-*")), [])

    def test_pending_capture_blocks_recovery_before_file_access(self):
        with tempfile.TemporaryDirectory() as raw:
            capture = CaptureDrainer(None, Path(raw))
            capture.spool = object()
            with self.assertRaisesRegex(RuntimeError, "pending capture"):
                capture.recover(".missing.partial.wav")
