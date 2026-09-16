import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from daw_production import OfflineRenderer


class ResampleContinuityTests(unittest.TestCase):
    def test_block_partition_does_not_change_samples(self):
        for rate in (32000, 44100, 48000, 88200, 96000, 192000):
            with self.subTest(rate=rate), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                with wave.open(str(root / "signal.wav"), "wb") as output:
                    output.setnchannels(2); output.setsampwidth(2); output.setframerate(rate)
                    output.writeframes(b"".join(struct.pack("<hh", (i * 317) % 30000, -((i * 137) % 30000)) for i in range(1000)))
                reader = OfflineRenderer(root)
                expected = reader._source_slice("signal.wav", 137, 4096)
                left, right = [], []
                position = 137
                for count in (1, 7, 255, 256, 511, 1024, 2042):
                    l, r = reader._source_slice("signal.wav", position, count)
                    left.extend(l); right.extend(r); position += count
                self.assertEqual(len(left), len(expected[0]))
                for channel, reference in zip((left, right), expected):
                    self.assertTrue(channel == reference, f"partition changes samples at {rate} Hz")
