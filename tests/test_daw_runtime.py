import struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from daw_runtime import RecordingSpool,playback_prefetch_plan
class DawRuntimeTests(unittest.TestCase):
 def test_prefetch_keeps_disk_out_of_callback(self):
  session={"sessionId":"x","revision":1,"tracks":[{"trackId":"t","clips":[{"clipId":"c","startFrame":0,"lengthFrames":100,"source":{"type":"audio-file","uri":"x.wav"}}]}]};plan=playback_prefetch_plan(session,0);self.assertFalse(plan["diskIoInAudioCallback"]);self.assertFalse(plan["physicalOutputsArmed"])
 def test_recording_requires_arm_and_finishes_atomically(self):
  with tempfile.TemporaryDirectory() as raw:
   spool=RecordingSpool(Path(raw))
   with self.assertRaises(PermissionError):spool.begin("t")
   spool.begin("t",acknowledge_physical_input=True);spool.append_s32(struct.pack("<ii",1,-1),1);spool.dropout(1,2);done=spool.finish("take.wav");self.assertTrue(done["atomicCompletion"]);self.assertTrue(done["directoryDurable"]);self.assertFalse(done["partialCleanupPending"]);self.assertFalse(done["dropoutFree"]);self.assertFalse(done["physicalInputArmed"])
if __name__=="__main__":unittest.main()
