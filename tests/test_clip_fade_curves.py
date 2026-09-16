import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from clip_fades import fade_envelope
from daw_session import normalize_session


class FadeCurveTests(unittest.TestCase):
    def test_linear_and_equal_power_midpoints_and_sustain(self):
        region = {"renderFrames": 20, "fades": {"inFrames": 10, "outFrames": 10, "curve": "linear"}}
        self.assertEqual(fade_envelope(region, 4), .5)
        self.assertEqual(fade_envelope(region, 15), .5)
        region["fades"]["curve"] = "equal-power"
        self.assertAlmostEqual(fade_envelope(region, 4), math.sqrt(.5))
        self.assertAlmostEqual(fade_envelope(region, 15), math.sqrt(.5))
        self.assertEqual(fade_envelope(region, 9), 1)
        self.assertEqual(fade_envelope(region, 10), 1)
        region["clipOffsetFrames"] = 4
        self.assertAlmostEqual(fade_envelope(region, 0), math.sqrt(.5))

    def test_unknown_curve_is_rejected_by_session_validation(self):
        with self.assertRaisesRegex(ValueError, "fade curve"):
            normalize_session({"tracks": [{"trackId": "t", "clips": [{"clipId": "c", "lengthFrames": 10, "source": {"type": "generator"}, "fades": {"curve": "unknown"}}]}]})
