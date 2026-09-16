import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from hardware_qualification import probe_platform,validate_le_uwb_plan
class HardwareQualificationTests(unittest.TestCase):
 def test_absent_hardware_never_qualifies(self):
  with tempfile.TemporaryDirectory() as raw:
   result=probe_platform(sys_root=Path(raw)/"sys",dev_root=Path(raw)/"dev")
   self.assertFalse(result["audio"]["qualified"]);self.assertFalse(result["physicalOutputsArmed"])
 def test_timing_plan(self):
  result=validate_le_uwb_plan({"isoIntervalUs":7500,"presentationDelayUs":30000,"uwbUpdateHz":50})
  self.assertTrue(result["leAudioCarriesProgram"]);self.assertFalse(result["uwbCarriesProgram"])
if __name__=="__main__":unittest.main()
