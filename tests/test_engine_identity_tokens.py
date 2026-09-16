import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from audio_identity import describe_audio_device
from midi_identity import describe_midi_device


class EngineIdentityTokenTests(unittest.TestCase):
    def test_wasapi_engine_stable_token_is_reconnectable(self):
        stable = "sha256:" + "a" * 64
        native = "sha256:" + "b" * 64
        device = {
            "id": "wasapi-1",
            "backend": "wasapi",
            "address": f"native={native};persistent={stable};strength=os-stable-endpoint;auto=1",
            "output": True,
        }
        identity = describe_audio_device(device)
        self.assertEqual(identity["identityStrength"], "os-stable-endpoint")
        self.assertTrue(identity["automaticReconnectEligible"])
        self.assertNotIn(stable, identity["persistentId"])

    def test_wasapi_engine_installation_token_never_auto_reconnects(self):
        persistent = "sha256:" + "c" * 64
        native = "sha256:" + "d" * 64
        identity = describe_audio_device({
            "id": "wasapi-2",
            "backend": "wasapi",
            "address": f"native={native};persistent={persistent};strength=installation-snapshot;auto=0",
            "output": True,
        })
        self.assertEqual(identity["identityStrength"], "installation-snapshot")
        self.assertFalse(identity["automaticReconnectEligible"])
        self.assertIsNotNone(identity["persistentId"])

    def test_coreaudio_engine_token_is_reconnectable(self):
        persistent = "sha256:" + "e" * 64
        native = "sha256:" + "f" * 64
        identity = describe_audio_device({
            "id": "coreaudio-1",
            "backend": "coreaudio",
            "address": f"native={native};persistent={persistent};strength=os-stable-endpoint;auto=1",
            "input": True,
            "output": True,
        })
        self.assertEqual(identity["identityStrength"], "os-stable-endpoint")
        self.assertTrue(identity["automaticReconnectEligible"])

    def test_coremidi_engine_path_uses_strong_hash_only_identity(self):
        persistent = "sha256:" + "1" * 64
        native = "sha256:" + "2" * 64
        identity = describe_midi_device({
            "id": "coremidi-1",
            "path": f"backend=coremidi;native={native};persistent={persistent};strength=os-stable-endpoint;auto=1",
        })
        self.assertEqual(identity["identityStrength"], "os-stable-endpoint")
        self.assertTrue(identity["automaticRebindEligible"])
        self.assertNotIn(persistent, identity["persistentId"])

    def test_windows_midi_installation_token_is_pinned_but_not_auto_rebound(self):
        persistent = "sha256:" + "3" * 64
        native = "sha256:" + "4" * 64
        identity = describe_midi_device({
            "id": "windows-midi-1",
            "path": f"backend=windows-midi;native={native};persistent={persistent};strength=installation-snapshot;auto=0",
        })
        self.assertEqual(identity["identityStrength"], "installation-snapshot")
        self.assertFalse(identity["automaticRebindEligible"])
        self.assertIsNotNone(identity["persistentId"])

    def test_malformed_engine_tokens_never_gain_rebind_authority(self):
        audio = describe_audio_device({
            "id": "x", "backend": "wasapi",
            "address": "native=raw-private;pending=oops;persistent=raw-private;strength=os-stable-endpoint;auto=1",
            "output": True,
        })
        midi = describe_midi_device({
            "id": "y",
            "path": "backend=coremidi;native=private;persistent=private;strength=os-stable-endpoint;auto=1",
        })
        self.assertFalse(audio["automaticReconnectEligible"])
        self.assertIsNone(audio["persistentId"])
        self.assertFalse(midi["automaticRebindEligible"])
        self.assertIsNone(midi["persistentId"])


if __name__ == "__main__":
    unittest.main()
