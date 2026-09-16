import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from audio_conversion import audio_conversion_plan

class AudioConversionTests(unittest.TestCase):
    def test_exact_float_stereo_needs_no_policy(self):
        plan=audio_conversion_plan({"sampleRate":192000,"format":"FLOAT_LE","channels":2},None,direction="playback")
        self.assertFalse(plan["requiresConversion"]);self.assertEqual(plan["nativeConversionFlags"],0)
    def test_rate_integer_and_channel_changes_each_require_explicit_choice(self):
        device={"sampleRate":48000,"format":"S24_3LE","channels":1}
        for policy,marker in (({},"sample-rate"),({"sampleRate":"bounded-sinc"},"integer PCM"),({"sampleRate":"bounded-sinc","sampleFormat":"normalize-integer"},"channel conversion")):
            with self.subTest(policy=policy),self.assertRaisesRegex(ValueError,marker):audio_conversion_plan(device,policy,direction="capture")
        plan=audio_conversion_plan(device,{"sampleRate":"bounded-sinc","sampleFormat":"normalize-integer","channels":"mono-to-stereo"},direction="capture")
        self.assertEqual(plan["nativeConversionFlags"],7);self.assertFalse(plan["upscalingRestoresMissingBandwidth"])
    def test_playback_downmix_is_a_distinct_choice(self):
        with self.assertRaisesRegex(ValueError,"stereo-to-mono"):audio_conversion_plan({"sampleRate":192000,"format":"FLOAT_LE","channels":1},{},direction="playback")
        plan=audio_conversion_plan({"sampleRate":192000,"format":"FLOAT_LE","channels":1},{"channels":"stereo-to-mono"},direction="playback")
        self.assertEqual(plan["conversions"][0]["matrix"]["mono"],"0.5*left+0.5*right")

    def test_multichannel_matrix_is_explicit_and_deterministic(self):
        policy={"channels":"explicit-matrix"}
        playback=audio_conversion_plan({"sampleRate":192000,"format":"FLOAT_LE","channels":8},policy,direction="playback")
        capture=audio_conversion_plan({"sampleRate":192000,"format":"FLOAT_LE","channels":8},policy,direction="capture")
        for plan in (playback,capture):
            matrix=plan["conversions"][0]["matrix"]
            self.assertEqual(matrix["canonicalLeft"],0);self.assertEqual(matrix["canonicalRight"],1)
            self.assertEqual(matrix["additionalDeviceChannels"],"silence-on-playback-ignore-on-capture")

if __name__=="__main__":unittest.main()
