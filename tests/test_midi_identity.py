import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from midi_identity import MidiIdentityStore, describe_midi_device


class MidiIdentityTests(unittest.TestCase):
    def fixture(self, root, serial=None):
        root = Path(root); usb = root / "devices/usb/1-2"; usb.mkdir(parents=True)
        (usb/"idVendor").write_text("1234"); (usb/"idProduct").write_text("abcd")
        if serial is not None: (usb/"serial").write_text(serial)
        sound = usb/"sound/card0"; sound.mkdir(parents=True)
        (root/"class/sound").mkdir(parents=True)
        (root/"class/sound/midiC0D1").symlink_to(sound)
        (root/"class/sound/card0").mkdir(); (root/"class/sound/card0/id").write_text("Controller")
        return {"id":"linux-raw-0-1", "path":"/dev/snd/midiC0D1"}

    def test_serial_identity_is_stable_private_and_rebindable(self):
        with tempfile.TemporaryDirectory() as raw:
            device = self.fixture(raw, "private-serial")
            first = describe_midi_device(device, sys_root=Path(raw))
            second = describe_midi_device({**device,"name":"Renamed"}, sys_root=Path(raw))
            self.assertEqual(first["persistentId"], second["persistentId"])
            self.assertTrue(first["automaticRebindEligible"])
            self.assertNotIn("private-serial", json.dumps(first))

    def test_topology_identity_requires_explicit_rebind(self):
        with tempfile.TemporaryDirectory() as raw:
            identity = describe_midi_device(self.fixture(raw), sys_root=Path(raw))
            self.assertEqual(identity["identityStrength"], "topology")
            self.assertFalse(identity["automaticRebindEligible"])

    def test_registry_requires_exact_recorded_stable_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            store = MidiIdentityStore(Path(raw)/"identities.json")
            stable = {"persistentId":"midi-a", "identityStrength":"hardware-serial", "automaticRebindEligible":True, "usbHardwareId":"USB:1234:ABCD"}
            store.record("linux-raw-0-1", stable)
            self.assertTrue(MidiIdentityStore(store.path).permits_rebind("linux-raw-0-1", stable))
            self.assertFalse(store.permits_rebind("linux-raw-0-1", {**stable,"persistentId":"midi-b"}))
            self.assertFalse(store.permits_rebind("other", stable))


    def test_observation_cannot_replace_pinned_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            store=MidiIdentityStore(Path(raw)/"identities.json")
            first={"persistentId":"midi-a","identityStrength":"os-stable-endpoint","automaticRebindEligible":True}
            replacement={"persistentId":"midi-b","identityStrength":"os-stable-endpoint","automaticRebindEligible":True}
            store.record("endpoint",first);observed=store.record("endpoint",replacement)
            self.assertEqual(observed["persistentId"],"midi-a")
            self.assertEqual(MidiIdentityStore(store.path).expected("endpoint")["persistentId"],"midi-a")

    def test_reconnect_match_requires_exact_unique_persistent_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            store=MidiIdentityStore(Path(raw)/"identities.json")
            stable={"persistentId":"midi-a","identityStrength":"os-stable-endpoint","automaticRebindEligible":True}
            store.record("old",stable)
            replacement={"id":"new","connected":True,**stable}
            self.assertIs(store.reconnect_match("old",[replacement]),replacement)
            self.assertIsNone(store.reconnect_match("old",[replacement,{**replacement,"id":"duplicate"}]))
    def test_volatile_endpoint_is_never_persisted(self):
        with tempfile.TemporaryDirectory() as raw:
            store = MidiIdentityStore(Path(raw)/"identities.json")
            identity = describe_midi_device({"path":"virtual"}, sys_root=Path(raw))
            self.assertIsNone(store.record("virtual", identity))
            self.assertFalse(store.path.exists())


class CrossPlatformMidiIdentityTests(unittest.TestCase):
    def test_coremidi_unique_id_hash_is_rebindable(self):
        identity=describe_midi_device({"backend":"coremidi","uniqueIdHash":"sha256:"+"d"*64})
        self.assertEqual(identity["identityStrength"],"os-stable-endpoint");self.assertTrue(identity["automaticRebindEligible"]);self.assertTrue(identity["persistentId"].startswith("midi-"))

    def test_windows_midi_requires_verified_persistent_identity(self):
        token="sha256:"+"e"*64
        weak=describe_midi_device({"backend":"windows-midi","persistentIdHash":token,"persistentIdentityVerified":False})
        self.assertIsNone(weak["persistentId"]);self.assertFalse(weak["automaticRebindEligible"])
        strong=describe_midi_device({"backend":"windows-midi","persistentIdHash":token,"persistentIdentityVerified":True})
        self.assertEqual(strong["identityStrength"],"os-stable-endpoint");self.assertTrue(strong["automaticRebindEligible"])

    def test_cross_platform_midi_identity_rejects_raw_private_tokens(self):
        for device in ({"backend":"coremidi","uniqueIdHash":"private"},{"backend":"windows-midi","persistentIdHash":"private","persistentIdentityVerified":True}):
            identity=describe_midi_device(device);self.assertIsNone(identity["persistentId"]);self.assertFalse(identity["automaticRebindEligible"])
