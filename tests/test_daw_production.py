import json,math,struct,sys,tempfile,unittest,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from daw_production import AutosaveStore,MediaLibrary,OfflineRenderer,PluginCatalog,TakeManager,automation_value,beat_to_frame
class DawProductionTests(unittest.TestCase):
 def wav(self,path,rate=48000,frames=480):
  with wave.open(str(path),"wb") as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b"".join(struct.pack("<h",round(math.sin(i/8)*12000)) for i in range(frames)))
 def session(self,uri):return {"sessionId":"mix","revision":1,"tracks":[{"trackId":"t","kind":"audio","pan":0,"gain":1,"clips":[{"clipId":"c","startFrame":0,"lengthFrames":1920,"source":{"type":"audio-file","uri":uri},"fades":{"inFrames":10,"outFrames":10}}]}]}
 def test_tempo_and_automation(self):
  self.assertEqual(beat_to_frame([{"beat":0,"bpm":120,"numerator":4,"denominator":4}],4),384000);self.assertEqual(automation_value([{"frame":0,"value":0},{"frame":100,"value":1}],50,0),.5)
 def test_media_ingest_deduplicates_and_take_contract(self):
  with tempfile.TemporaryDirectory() as raw:
   source=Path(raw)/"source.wav";self.wav(source);library=MediaLibrary(Path(raw)/"media");a=library.ingest(source);b=library.ingest(source);self.assertFalse(a["deduplicated"]);self.assertTrue(b["deduplicated"]);self.assertTrue(library.verify(a["managedPath"],a["contentHash"])["verified"])
   take=TakeManager(Path(raw)/"media").prepare("t",0,pre_roll_frames=100);self.assertFalse(take["physicalInputArmed"])
 def test_deterministic_render_receipt(self):
  with tempfile.TemporaryDirectory() as raw:
   media=Path(raw)/"media";media.mkdir();self.wav(media/"tone.wav");renderer=OfflineRenderer(media)
   a=renderer.render(self.session("tone.wav"),Path(raw)/"a.wav",0,1920,bits=16,seed=7);b=renderer.render(self.session("tone.wav"),Path(raw)/"b.wav",0,1920,bits=16,seed=7);self.assertEqual(a["outputSha256"],b["outputSha256"]);self.assertFalse(a["physicalOutputsArmed"])
 def test_plugin_quarantine_and_autosave_boundaries(self):
  with tempfile.TemporaryDirectory() as raw:
   manifests=Path(raw)/"plugins";manifests.mkdir();(manifests/"p.json").write_text(json.dumps({"pluginId":"p","format":"builtin"}));catalog=PluginCatalog(manifests);catalog.quarantine("p","crash");self.assertTrue(catalog.scan()["plugins"][0]["quarantined"])
   receipt=AutosaveStore(Path(raw)/"autosave").save(self.session("tone.wav"));self.assertTrue(receipt["recoverable"])
if __name__=="__main__":unittest.main()
