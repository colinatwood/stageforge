import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from staged_resources import StagedFile,StagedResourceRegistry
from temporary_ownership import create_owner_manifest


class StagedResourceTests(unittest.TestCase):
    def test_publish_removes_owner_evidence_and_never_overwrites_contract(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);staged=StagedFile(root,prefix=".render-",suffix=".wav",resource_class="render-output",purpose="offline-render-publication")
            staged.path.write_bytes(b"complete");owner=staged.owner_path;target=root/"mix.wav";staged.publish(target);staged.close()
            self.assertEqual(target.read_bytes(),b"complete");self.assertFalse(owner.exists());self.assertFalse(staged.path.exists())

    def test_status_and_reclaim_are_bounded_and_conservative(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);imports=root/"objects";renders=root/"exports";imports.mkdir();renders.mkdir()
            live=StagedFile(imports,prefix=".media-",suffix="",resource_class="media-import",purpose="content-addressed-import")
            dead=StagedFile(renders,prefix=".render-",suffix=".wav",resource_class="render-output",purpose="offline-render-publication")
            owner=json.loads(dead.owner_path.read_text());owner["pid"]=99999999;dead.owner_path.write_text(json.dumps(owner))
            orphan=renders/".render-orphan.wav";orphan.write_bytes(b"unknown")
            registry=StagedResourceRegistry([("media-import",imports,".media-*"),("render-output",renders,".render-*.wav")]);status=registry.status()
            self.assertEqual(status["resourceCount"],3);self.assertEqual(status["liveCount"],1);self.assertEqual(status["reclaimableCount"],1);self.assertEqual(status["unknownOwnerCount"],1)
            self.assertNotIn(str(root),json.dumps(status));self.assertNotIn('"pid"',json.dumps(status))
            cleaned=registry.reclaim();self.assertEqual(cleaned["reclaimedCount"],1);self.assertFalse(dead.path.exists());self.assertTrue(live.path.exists());self.assertTrue(orphan.exists())
            live.close()

    def test_legacy_dead_owner_is_unknown_and_preserved(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);path=root/".render-legacy.wav";path.write_bytes(b"legacy")
            Path(str(path)+".owner.json").write_text(json.dumps({"pid":99999999,"createdAtUnixMs":1}))
            registry=StagedResourceRegistry([("render-output",root,".render-*.wav")])
            status=registry.status();self.assertEqual(status["unknownOwnerCount"],1);self.assertEqual(status["reclaimableCount"],0)
            cleaned=registry.reclaim();self.assertEqual(cleaned["reclaimedCount"],0);self.assertTrue(path.exists())

    def test_replaced_inode_is_unknown_even_when_recorded_owner_is_dead(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);staged=StagedFile(root,prefix=".render-",suffix=".wav",resource_class="render-output",purpose="offline-render-publication")
            owner=json.loads(staged.owner_path.read_text());owner["pid"]=99999999;staged.owner_path.write_text(json.dumps(owner))
            replacement=root/"replacement";replacement.write_bytes(b"new-object");os.replace(replacement,staged.path)
            registry=StagedResourceRegistry([("render-output",root,".render-*.wav")])
            status=registry.status();self.assertEqual(status["unknownOwnerCount"],1);self.assertEqual(status["reclaimableCount"],0)
            self.assertEqual(registry.reclaim()["reclaimedCount"],0);self.assertEqual(staged.path.read_bytes(),b"new-object")
            staged.close()

    def test_failed_stage_creation_cleans_data_when_manifest_publish_fails(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            with patch("staged_resources.create_owner_manifest",side_effect=OSError("disk")),self.assertRaises(OSError):
                StagedFile(root,prefix=".media-",suffix="",resource_class="media-import",purpose="import")
            self.assertEqual(list(root.iterdir()),[])


if __name__=="__main__":unittest.main()
