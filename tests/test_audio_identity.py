import tempfile,sys,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from audio_identity import AudioIdentityStore,describe_audio_device


class AudioIdentityTests(unittest.TestCase):
    def test_reused_native_id_does_not_overwrite_pinned_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/"identities.json";store=AudioIdentityStore(path)
            original={"persistentId":"audio-a","automaticReconnectEligible":True}
            replacement={"id":"old","persistentId":"audio-b","automaticReconnectEligible":True,"connected":True,"output":True}
            store.record("old",original);saved=path.read_bytes()
            store.record("old",replacement)
            self.assertEqual(path.read_bytes(),saved)
            self.assertIsNone(store.resolve("old",[replacement],"output"))
            moved={**replacement,"id":"new","persistentId":"audio-a"}
            self.assertIs(store.resolve("old",[replacement,moved],"output"),moved)
            self.assertEqual(AudioIdentityStore(path).expected("old")["persistentId"],"audio-a")

    def test_duplicate_serial_is_rejected_even_at_original_native_id(self):
        with tempfile.TemporaryDirectory() as raw:
            store=AudioIdentityStore(Path(raw)/"identities.json")
            device={"id":"old","persistentId":"audio-a","automaticReconnectEligible":True,"connected":True,"output":True}
            store.record("old",device)
            self.assertIsNone(store.resolve("old",[device,{**device,"id":"new"}],"output"))

    def test_explicit_replace_returns_prior_record_and_persists_new_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/"identities.json";store=AudioIdentityStore(path)
            store.record("old",{"persistentId":"audio-a","identityStrength":"hardware-serial","automaticReconnectEligible":True})
            previous,current=store.replace("old",{"persistentId":"audio-b","identityStrength":"topology","automaticReconnectEligible":False})
            self.assertEqual(previous["persistentId"],"audio-a");self.assertEqual(current["persistentId"],"audio-b")
            self.assertEqual(AudioIdentityStore(path).expected("old"),current);self.assertTrue(current["explicitlyRebound"])

    def test_explicit_replace_requires_existing_and_persistent_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            store=AudioIdentityStore(Path(raw)/"identities.json")
            with self.assertRaisesRegex(ValueError,"no persistent identity"):store.replace("old",{})
            with self.assertRaisesRegex(ValueError,"no pinned identity"):store.replace("old",{"persistentId":"audio-b"})

    def test_empty_and_malformed_addresses_remain_volatile(self):
        for address in ("", "hw:2,0junk", "hw:2,0 extra", "hw:2,0,1"):
            self.assertIsNone(describe_audio_device({"id":"x","backend":"alsa","address":address})["persistentId"])

    def fixture(self,raw,serial="SERIAL-123"):
        root=Path(raw);sys_root=root/"sys";proc_root=root/"proc";usb=sys_root/"devices"/"usb1"/"1-2";usb.mkdir(parents=True)
        (usb/"idVendor").write_text("1234");(usb/"idProduct").write_text("abcd")
        if serial:(usb/"serial").write_text(serial)
        node=sys_root/"class"/"sound"/"card2";node.mkdir(parents=True);(node/"device").symlink_to(usb,target_is_directory=True)
        card=proc_root/"asound"/"card2";card.mkdir(parents=True);(card/"id").write_text("StageUSB")
        return sys_root,proc_root
    def test_serial_identity_survives_native_card_renumber(self):
        with tempfile.TemporaryDirectory() as raw:
            sys_root,proc_root=self.fixture(raw);device={"id":"alsa-old","backend":"alsa","address":"hw:2,0","input":True,"output":True}
            identity=describe_audio_device(device,sys_root=sys_root,proc_root=proc_root);self.assertEqual(identity["identityStrength"],"hardware-serial");self.assertTrue(identity["automaticReconnectEligible"])
            store=AudioIdentityStore(Path(raw)/"identities.json");store.record("alsa-old",identity)
            replacement={"id":"alsa-new",**identity};self.assertEqual(store.reconnect_match("alsa-old",[replacement])["id"],"alsa-new")
    def test_topology_identity_never_automatically_reconnects(self):
        with tempfile.TemporaryDirectory() as raw:
            sys_root,proc_root=self.fixture(raw,serial="");identity=describe_audio_device({"id":"old","backend":"alsa","address":"hw:CARD=StageUSB,DEV=0","input":False,"output":True},sys_root=sys_root,proc_root=proc_root)
            self.assertEqual(identity["identityStrength"],"topology");store=AudioIdentityStore(Path(raw)/"identities.json");store.record("old",identity);self.assertIsNone(store.reconnect_match("old",[{"id":"new",**identity}]))
    def test_alias_and_null_identity_are_explicit(self):
        self.assertIsNone(describe_audio_device({"id":"x","backend":"alsa","address":"default"})["persistentId"])
        self.assertEqual(describe_audio_device({"id":"null-audio"})["persistentId"],"audio-null")

    def test_wasapi_stable_id_hash_is_reconnectable_but_installation_snapshot_is_not(self):
        stable="sha256:"+"a"*64; snapshot="sha256:"+"b"*64
        identity=describe_audio_device({"id":"w1","backend":"wasapi","stableIdHash":stable,"instanceIdHash":snapshot,"output":True})
        self.assertEqual(identity["identityStrength"],"os-stable-endpoint");self.assertTrue(identity["automaticReconnectEligible"]);self.assertTrue(identity["persistentId"].startswith("audio-"))
        weak=describe_audio_device({"id":"w2","backend":"wasapi","instanceIdHash":snapshot,"output":True})
        self.assertEqual(weak["identityStrength"],"installation-snapshot");self.assertFalse(weak["automaticReconnectEligible"]);self.assertIsNotNone(weak["persistentId"])

    def test_coreaudio_uid_hash_is_reconnectable_without_exporting_raw_identity(self):
        uid_hash="sha256:"+"c"*64
        identity=describe_audio_device({"id":"m1","backend":"coreaudio","uidHash":uid_hash,"input":True,"output":True})
        self.assertEqual(identity["identityStrength"],"os-stable-endpoint");self.assertTrue(identity["automaticReconnectEligible"]);self.assertNotIn(uid_hash,identity["persistentId"])

    def test_cross_platform_audio_identity_rejects_unhashed_tokens(self):
        for device in ({"backend":"wasapi","stableIdHash":"raw-private-id","output":True},{"backend":"coreaudio","uidHash":"raw-private-uid","input":True}):
            identity=describe_audio_device(device);self.assertIsNone(identity["persistentId"]);self.assertFalse(identity["automaticReconnectEligible"])


if __name__=="__main__":unittest.main()
