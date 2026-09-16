import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from punch_capture import PunchCaptureGate

class PunchCaptureGateTests(unittest.TestCase):
 def test_generation_punch_preroll_and_latency_window(self):
  gate=PunchCaptureGate(2,punch_in_frame=100,punch_out_frame=300,pre_roll_frames=50,latency_compensation_frames=10)
  self.assertEqual(gate.select({"generation":1,"showFrame":40,"frames":20}),[])
  first=gate.select({"generation":2,"showFrame":40,"frames":100});self.assertEqual((first[0].offset,first[0].frames),(20,80))
  second=gate.select({"generation":2,"showFrame":140,"frames":200});self.assertEqual(second[0].frames,170)
  status=gate.status();self.assertTrue(status["punchComplete"]);self.assertEqual(status["selectedFrames"],250);self.assertEqual(status["staleBlocks"],1)
 def test_loop_capture_splits_passes_at_exact_boundaries(self):
  gate=PunchCaptureGate(1,punch_in_frame=100,pre_roll_frames=10,loop_start_frame=100,loop_end_frame=200,maximum_passes=2)
  slices=gate.select({"generation":1,"showFrame":90,"frames":210})
  self.assertEqual([(s.frames,s.loop_pass) for s in slices],[(10,0),(100,0),(100,1)])
  self.assertEqual(gate.status()["completedPasses"],2);self.assertTrue(gate.status()["punchComplete"])
if __name__=="__main__":unittest.main()
