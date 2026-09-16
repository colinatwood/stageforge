import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from plugin_latency import latency_compensation_plan
class PluginLatencyTests(unittest.TestCase):
 def test_parallel_paths_align_to_slowest(self):
  plan=latency_compensation_plan([{"pathId":"dry","latencyFrames":0},{"pathId":"fx","latencyFrames":512}]);self.assertEqual(plan["paths"][0]["compensationFrames"],512);self.assertEqual(plan["paths"][1]["compensationFrames"],0);self.assertTrue(plan["latencyAligned"])
 def test_capacity_fails_closed(self):
  with self.assertRaises(ValueError):latency_compensation_plan([{"pathId":"x","latencyFrames":70000}])
 def test_empty_plan_fails_closed(self):
  with self.assertRaises(ValueError):latency_compensation_plan([])
if __name__=="__main__":unittest.main()
