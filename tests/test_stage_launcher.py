import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from stage_launcher import launcher_projection

class StageLauncherTests(unittest.TestCase):
 def test_projection_bounds_pads_and_preserves_safety(self):
  assets=[{"resourceId":f"clip-{i}","mode":"oneshot","registered":True} for i in range(10)]
  result=launcher_projection({"revision":7,"transport":{"running":True,"seconds":2,"bpm":128,"key":"D"}},
   {"assets":assets},{"state":"recording","physicalInputArmed":True,"dropoutBlocks":2},{"sequence":3,"source":"midi"})
  self.assertEqual(len(result["pads"]),8);self.assertEqual(result["pads"][0]["shortcut"],"1");self.assertEqual(result["pads"][-1]["shortcut"],"8")
  self.assertEqual(result["authority"],"core");self.assertFalse(result["physicalOutputsArmed"]);self.assertTrue(result["capture"]["physicalInputArmed"])
 def test_duplicate_asset_modes_produce_one_pad(self):
  result=launcher_projection({"transport":{}},{"assets":[{"resourceId":"clip","mode":"oneshot","registered":True},{"resourceId":"clip","mode":"loop","registered":True}]},{},None)
  self.assertEqual(len(result["pads"]),1)

if __name__=="__main__":unittest.main()
