import errno
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from audio_preflight import AlsaProbe, audio_preflight, validate_request


class AudioPreflightTests(unittest.TestCase):
    def test_bad_requests_never_open_device(self):
        factory = Mock()
        for data in (None, [], {}, {"address":"default"}, {"address":"hw:0,0", "sampleRate":True},
                     {"address":"hw:0,0", "channels":0}, {"address":"hw:0,0", "periodFrames":1.5},
                     {"address":"hw:0,0", "format":"unknown"}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                audio_preflight(data, system="Linux", probe_factory=factory)
        factory.assert_not_called()

    def test_unknown_is_distinct_from_unsupported(self):
        cases = [("complete", 0, "constraints-supported", True),
                 ("sampleRate", -errno.EINVAL, "constraints-unsupported", False),
                 ("open", -errno.EINVAL, "probe-error", None),
                 ("open", -errno.EBUSY, "busy", None),
                 ("open", -errno.EACCES, "permission-denied", None),
                 ("open", -errno.ENODEV, "disconnected-or-missing", None)]
        for stage, code, state, support in cases:
            with self.subTest(state=state):
                report = audio_preflight({"address":"hw:0,0"}, system="Linux", probe_factory=lambda: Mock(check=lambda _: (stage,code)))
                self.assertEqual(report["status"], state)
                self.assertIs(report["supported"], support)
                self.assertFalse(report["streamStarted"])

    def test_missing_library_and_other_os(self):
        factory = Mock(side_effect=OSError())
        self.assertEqual(audio_preflight({"address":"hw:0,0"}, system="Linux", probe_factory=factory)["status"], "unavailable")
        factory.reset_mock()
        self.assertIsNone(audio_preflight({"address":"hw:0,0"}, system="Darwin", probe_factory=factory)["supported"])
        factory.assert_not_called()

    def test_constraints_are_combined_and_resources_closed(self):
        for failing_stage in (None, "rate", "any", "malloc"):
            with self.subTest(stage=failing_stage):
                lib = Mock()
                for name in ("open", "close", "hw_params_malloc", "hw_params_any", "hw_params_set_access", "hw_params_set_format", "hw_params_set_channels", "hw_params_set_rate", "hw_params_set_period_size"):
                    getattr(lib,"snd_pcm_"+name).return_value = 0
                lib.snd_pcm_format_value.return_value = 14
                if failing_stage:
                    name = {"rate":"set_rate", "any":"any", "malloc":"malloc"}[failing_stage]
                    getattr(lib, "snd_pcm_hw_params_"+name).return_value = -errno.EINVAL
                probe = AlsaProbe.__new__(AlsaProbe)
                probe.lib = lib
                stage, code = probe.check(validate_request({"address":"hw:0,0"}))
                lib.snd_pcm_close.assert_called_once()
                self.assertEqual(lib.snd_pcm_hw_params_free.call_count, 0 if failing_stage == "malloc" else 1)
                lib.snd_pcm_hw_params.assert_not_called()
                lib.snd_pcm_start.assert_not_called()
                if failing_stage == "rate":
                    lib.snd_pcm_hw_params_set_period_size.assert_not_called()
                if failing_stage is None:
                    self.assertEqual((stage,code), ("complete",0))
                    calls = lib.mock_calls
                    self.assertLess(next(i for i,c in enumerate(calls) if c[0]=="snd_pcm_hw_params_set_channels"), next(i for i,c in enumerate(calls) if c[0]=="snd_pcm_hw_params_set_rate"))
