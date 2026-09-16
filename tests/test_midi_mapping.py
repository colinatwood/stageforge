import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from midi_mapping import MidiMappingEngine

class MidiMappingTests(unittest.TestCase):
 def test_learn_next_knob_and_restore(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/"maps.json";engine=MidiMappingEngine(path);engine.begin({"targetId":"filter.cutoff","deviceId":"keys"})
   result=engine.observe({"deviceId":"keys","status":0xB2,"data1":74,"data2":64,"showTimeSeconds":.1},{"bpm":120,"key":"C"})
   self.assertEqual(result["learnedMapping"]["source"],{"deviceId":"keys","channel":2,"message":"cc","number":74});self.assertGreater(result["actions"][0]["value"],100)
   self.assertEqual(len(MidiMappingEngine(path).status()["mappings"]),1);self.assertEqual(json.loads(path.read_text())["schemaVersion"],1)
 def test_note_off_does_not_complete_learn(self):
  with tempfile.TemporaryDirectory() as raw:
   engine=MidiMappingEngine(Path(raw)/"maps.json");engine.begin({"targetId":"sample.trigger"});result=engine.observe({"deviceId":"pads","status":0x80,"data1":36,"data2":0},{"bpm":120,"key":"C"});self.assertIsNone(result["learnedMapping"]);self.assertIsNotNone(engine.status()["learning"])
 def test_pad_action_quantizes_and_key_syncs(self):
  with tempfile.TemporaryDirectory() as raw:
   engine=MidiMappingEngine(Path(raw)/"maps.json");engine.begin({"targetId":"instrument.note","quantize":"1/4","keySync":True,"scale":"major"});result=engine.observe({"deviceId":"pads","status":0x99,"data1":61,"data2":100,"showTimeSeconds":.26},{"bpm":120,"key":"C"});action=result["actions"][0];self.assertEqual(action["showTimeSeconds"],.5);self.assertEqual(action["outputNote"],60);self.assertEqual(action["transposeSemitones"],-1)
 def test_same_control_relearn_replaces_old_mapping(self):
  with tempfile.TemporaryDirectory() as raw:
   engine=MidiMappingEngine(Path(raw)/"maps.json")
   for target in ("filter.cutoff","filter.resonance"):
    engine.begin({"targetId":target});engine.observe({"deviceId":"x","status":0xB0,"data1":1,"data2":1},{"bpm":120,"key":"C"})
   self.assertEqual(len(engine.status()["mappings"]),1);self.assertEqual(engine.status()["mappings"][0]["target"]["targetId"],"filter.resonance")
 def test_endless_encoder_is_detected_from_relative_cc(self):
  with tempfile.TemporaryDirectory() as raw:
   engine=MidiMappingEngine(Path(raw)/"maps.json");engine.begin({"targetId":"track.pan"});result=engine.observe({"deviceId":"x","status":0xB0,"data1":10,"data2":1},{"bpm":120,"key":"C","running":False});self.assertEqual(result["learnedMapping"]["behavior"],"relative");self.assertGreater(result["actions"][0]["value"],0)
if __name__=="__main__":unittest.main()
