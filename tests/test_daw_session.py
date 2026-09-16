import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from daw_session import DawSessionStore,normalize_session,render_plan
class DawSessionTests(unittest.TestCase):
 def session(self):return {"sessionId":"show","revision":1,"futureField":{"keep":1},"tracks":[{"trackId":"vox","kind":"audio","solo":True,"clips":[{"clipId":"take-1","startFrame":100,"lengthFrames":400,"sourceOffsetFrames":20,"source":{"type":"audio-file","uri":"media/vox.wav","contentHash":"sha256:x"}}]},{"trackId":"band","kind":"audio","clips":[{"clipId":"band-1","startFrame":0,"lengthFrames":1000,"source":{"type":"audio-file","uri":"media/band.wav"}}]}]}
 def test_normalize_preserves_unknown_and_canonical_domain(self):
  value=normalize_session(self.session());self.assertEqual(value["sampleRate"],192000);self.assertEqual(value["futureField"]["keep"],1);self.assertFalse(value["physicalOutputsArmed"])
 def test_plan_applies_solo_and_non_destructive_offset(self):
  plan=render_plan(self.session(),200,600);self.assertEqual(len(plan["regions"]),1);self.assertEqual(plan["regions"][0]["sourceStartFrame"],120);self.assertTrue(plan["offline"])
 def test_store_requires_advancing_revision(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   with self.assertRaises(ValueError):store.save(self.session())
 def test_trim_split_fade_undo_redo(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   trimmed=store.edit({"op":"trim","clipId":"take-1","expectedRevision":1,"trimStartFrames":10,"trimEndFrames":20});self.assertEqual(trimmed["tracks"][0]["clips"][0]["lengthFrames"],370)
   split=store.edit({"op":"split","clipId":"take-1","expectedRevision":2,"splitFrame":200,"newClipId":"take-2"});self.assertEqual(len(split["tracks"][0]["clips"]),2)
   faded=store.edit({"op":"fade","clipId":"take-2","expectedRevision":3,"fadeInFrames":10,"fadeOutFrames":10});self.assertEqual(faded["tracks"][0]["clips"][1]["fades"]["curve"],"equal-power")
   self.assertEqual(len(store.undo()["tracks"][0]["clips"]),2);self.assertEqual(len(store.redo()["tracks"][0]["clips"]),2)
 def test_move_snaps_cross_track_and_rejects_stale_revision(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   moved=store.edit({"op":"move","clipId":"take-1","expectedRevision":1,"startFrame":251,"snapFrames":100,"targetTrackId":"band"})
   self.assertEqual([c["clipId"] for c in moved["tracks"][0]["clips"]],[])
   self.assertEqual(moved["tracks"][1]["clips"][1]["startFrame"],300)
   with self.assertRaisesRegex(ValueError,"expected revision 2"):
    store.edit({"op":"move","clipId":"take-1","expectedRevision":1,"startFrame":0})
   restored=store.undo();self.assertEqual(restored["tracks"][0]["clips"][0]["startFrame"],100)
 def test_move_rejects_incompatible_track(self):
  value=self.session();value["tracks"].append({"trackId":"keys","kind":"midi","clips":[]})
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(value)
   with self.assertRaisesRegex(ValueError,"incompatible"):
    store.edit({"op":"move","clipId":"take-1","expectedRevision":1,"startFrame":0,"targetTrackId":"keys"})
 def test_resize_trims_source_offset_and_is_one_undo_step(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   resized=store.edit({"op":"resize","clipId":"take-1","expectedRevision":1,"startFrame":200,"endFrame":400,"snapFrames":1})
   clip=resized["tracks"][0]["clips"][0];self.assertEqual((clip["startFrame"],clip["lengthFrames"],clip["sourceOffsetFrames"]),(200,200,120))
   restored=store.undo()["tracks"][0]["clips"][0];self.assertEqual((restored["startFrame"],restored["lengthFrames"],restored["sourceOffsetFrames"]),(100,400,20))
 def test_resize_rejects_extension_and_collapsed_snap(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   for start,end,snap in ((99,500,1),(100,501,1),(120,130,100)):
    with self.subTest(start=start,end=end,snap=snap),self.assertRaisesRegex(ValueError,"resize"):
     store.edit({"op":"resize","clipId":"take-1","expectedRevision":1,"startFrame":start,"endFrame":end,"snapFrames":snap})
 def test_atomic_group_move_preserves_offsets_and_undoes_once(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   moved=store.edit({"op":"moveMany","clipIds":["take-1","band-1"],"expectedRevision":1,"deltaFrames":96000,"snapFrames":96000})
   positions={clip["clipId"]:clip["startFrame"] for track in moved["tracks"] for clip in track["clips"]}
   self.assertEqual(positions,{"take-1":96100,"band-1":96000});self.assertEqual(moved["revision"],2)
   restored=store.undo();positions={clip["clipId"]:clip["startFrame"] for track in restored["tracks"] for clip in track["clips"]};self.assertEqual(positions,{"take-1":100,"band-1":0})
 def test_group_move_validates_every_clip_before_mutation(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session());before=store.load()
   for command in ({"clipIds":["take-1","missing"],"deltaFrames":1},{"clipIds":["take-1","take-1"],"deltaFrames":1},{"clipIds":["take-1","band-1"],"deltaFrames":-1000}):
    with self.subTest(command=command),self.assertRaises(ValueError):store.edit({"op":"moveMany","expectedRevision":1,"snapFrames":1,**command})
    self.assertEqual(store.load(),before)
 def test_marker_lifecycle_is_normalized_revisioned_and_undoable(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   added=store.marker_edit({"action":"add","markerId":"chorus","name":"Chorus","kind":"section","frame":192123,"expectedRevision":1});self.assertEqual(added["markers"][0]["frame"],192123)
   moved=store.marker_edit({"action":"move","markerId":"chorus","frame":288001,"snapFrames":96000,"expectedRevision":2});self.assertEqual(moved["markers"][0]["frame"],288000)
   deleted=store.marker_edit({"action":"delete","markerId":"chorus","expectedRevision":3});self.assertEqual(deleted["markers"],[])
   self.assertEqual(store.undo()["markers"][0]["markerId"],"chorus")
 def test_marker_rejects_duplicate_invalid_and_stale_without_mutation(self):
  value=self.session();value["markers"]=[{"markerId":"a","frame":0,"name":"A","kind":"cue"}]
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(value);before=store.load()
   for command in ({"action":"add","markerId":"a","frame":1},{"action":"move","markerId":"missing","frame":1},{"action":"delete","markerId":"a","expectedRevision":0}):
    with self.subTest(command=command),self.assertRaises(ValueError):store.marker_edit({"expectedRevision":1,**command})
    self.assertEqual(store.load(),before)
 def test_automation_upsert_delete_and_undo(self):
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(self.session())
   added=store.automation_edit({"action":"upsert","trackId":"vox","pointId":"v1","parameter":"volume","frame":192000,"value":0.5,"expectedRevision":1});point=added["tracks"][0]["automation"][0];self.assertEqual((point["frame"],point["value"],point["interpolation"]),(192000,0.5,"linear"))
   moved=store.automation_edit({"action":"upsert","trackId":"vox","pointId":"v1","parameter":"volume","frame":384000,"value":1.5,"expectedRevision":2});self.assertEqual(len(moved["tracks"][0]["automation"]),1)
   deleted=store.automation_edit({"action":"delete","trackId":"vox","pointId":"v1","expectedRevision":3});self.assertEqual(deleted["tracks"][0]["automation"],[])
   self.assertEqual(store.undo()["tracks"][0]["automation"][0]["pointId"],"v1")
 def test_automation_rejects_nonfinite_collision_and_stale_without_mutation(self):
  value=self.session();value["tracks"][0]["automation"]=[{"pointId":"v1","parameter":"volume","frame":100,"value":1}]
  with tempfile.TemporaryDirectory() as raw:
   store=DawSessionStore(Path(raw)/"daw.json");store.save(value);before=store.load()
   commands=({"action":"upsert","trackId":"vox","pointId":"v2","frame":100,"value":.5},{"action":"upsert","trackId":"vox","pointId":"v2","frame":200,"value":float("nan")},{"action":"delete","trackId":"vox","pointId":"missing"},{"action":"delete","trackId":"vox","pointId":"v1","expectedRevision":0})
   for command in commands:
    with self.subTest(command=command),self.assertRaises(ValueError):store.automation_edit({"expectedRevision":1,"parameter":"volume",**command})
    self.assertEqual(store.load(),before)
if __name__=="__main__":unittest.main()
