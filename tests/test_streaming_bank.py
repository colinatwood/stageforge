import hashlib,sys,tempfile,unittest,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from streaming_bank import StreamingSampleBanks
class Producer:
 def __init__(self):self.calls=[]
 def start_clip(self,session,clip_id,loop=False):self.calls.append((clip_id,loop));return {"generation":9}
class StreamingBankTests(unittest.TestCase):
 def test_replace_and_trigger_long_clip_without_native_preload(self):
  with tempfile.TemporaryDirectory() as raw:
   root=Path(raw);path=root/"long.wav"
   with wave.open(str(path),"wb") as out:out.setnchannels(2);out.setsampwidth(2);out.setframerate(48000);out.writeframes(b"\0\0"*2*100)
   digest="sha256:"+hashlib.sha256(path.read_bytes()).hexdigest();session={"tracks":[{"clips":[{"clipId":"long","lengthFrames":999999,"source":{"type":"audio-file","uri":"long.wav","contentHash":digest}}]}]}
   producer=Producer();banks=StreamingSampleBanks(root,producer);status=banks.replace(session,"show",[{"clipId":"long","loop":True}])
   self.assertEqual(status["banks"][0]["entries"][0]["frames"],999999);self.assertFalse(status["diskIoInAudioCallback"])
   result=banks.trigger(session,"show",0,"action-1");duplicate=banks.trigger(session,"show",0,"action-1");self.assertEqual(producer.calls,[('long',True)]);self.assertEqual(result["bankGeneration"],1);self.assertTrue(duplicate["deduplicated"]);self.assertFalse(result["physicalOutputsArmed"]);self.assertEqual(banks.status()["schemaVersion"],2)
 def test_replacement_advances_generation(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/"a.wav";path.write_bytes(b"x");digest="sha256:"+hashlib.sha256(b"x").hexdigest();session={"tracks":[{"clips":[{"clipId":"a","lengthFrames":1,"source":{"type":"audio-file","uri":"a.wav","contentHash":digest}}]}]};banks=StreamingSampleBanks(Path(raw),Producer())
   banks.replace(session,"b",[{"clipId":"a"}]);self.assertEqual(banks.replace(session,"b",[{"clipId":"a"}])["generation"],2)
if __name__=="__main__":unittest.main()
