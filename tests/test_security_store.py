import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from security_store import SecurityStateStore

class SecurityStoreTests(unittest.TestCase):
    def test_persists_identity_checkpoint_and_permissions(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/"security.json";first=SecurityStateStore(path)
            fingerprint=first.identity_fingerprint;first.checkpoint("1"*32,{"inboundSequence":7,"updatedUnixMs":9})
            second=SecurityStateStore(path)
            self.assertEqual(second.identity_fingerprint,fingerprint);self.assertEqual(second.session("1"*32)["inboundSequence"],7)
            self.assertEqual(os.stat(path).st_mode & 0o777,0o600);self.assertFalse(second.status()["physicalOutputsArmed"])
    def test_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/"security.json";SecurityStateStore(path)
            value=json.loads(path.read_text());value["keyEpoch"]=99;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):SecurityStateStore(path)

if __name__=="__main__":unittest.main()
