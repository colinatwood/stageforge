import shutil
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from daw_production import MediaLibrary


class MediaImportIntegrityTests(unittest.TestCase):
    def fixture(self, root):
        source = root / "input.wav"
        with wave.open(str(source), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(48000)
            output.writeframes(b"\x00\x20" * 100)
        return source, MediaLibrary(root / "media")

    def test_corrupt_existing_object_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as raw:
            source, library = self.fixture(Path(raw))
            first = library.ingest(source)
            self.assertTrue(library.ingest(source)["deduplicated"])
            target = library.root / first["managedPath"]
            target.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "managed media hash mismatch"):
                library.ingest(source)
            self.assertEqual(target.read_bytes(), b"corrupt")

    def test_source_changed_during_copy_does_not_publish(self):
        with tempfile.TemporaryDirectory() as raw:
            source, library = self.fixture(Path(raw))
            copyfile = shutil.copyfile
            def changing_copy(src, dst):
                with Path(src).open("ab") as output:
                    output.write(b"changed")
                return copyfile(src, dst)
            with patch("daw_production.shutil.copyfile", side_effect=changing_copy):
                with self.assertRaisesRegex(ValueError, "source changed during copy"):
                    library.ingest(source)
            self.assertEqual(list(library.objects.rglob("*.wav")), [])
            self.assertEqual(list(library.objects.rglob(".media-*")), [])
            self.assertEqual(list(library.objects.rglob("*.owner.json")), [])
