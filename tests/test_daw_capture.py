import sys,tempfile,time,unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from daw_capture import CaptureDrainer
from daw_runtime import RecordingSpool
class FakeCaptureNative:
 def __init__(self):self.available=True;self.armed=False;self.blocks=[{"sequence":1,"showFrame":0,"frames":2,"left":[.1,.2],"right":[-.1,-.2]},{"sequence":3,"showFrame":4,"frames":2,"left":[.3,.4],"right":[-.3,-.4]}]
 def daw_record_arm(self,track,ack):self.armed=ack
 def daw_record_disarm(self,track):self.armed=False
 def daw_record_pop(self,track):
  if self.blocks:return self.blocks.pop(0)
  raise RuntimeError("empty: record queue empty")
class CaptureDrainerTests(unittest.TestCase):
 def test_collision_retains_capture_for_new_filename(self):
  with tempfile.TemporaryDirectory() as raw:
   root=Path(raw);target=root/"existing.wav";target.write_bytes(b"previous")
   drain=CaptureDrainer(FakeCaptureNative(),root)
   try:
    drain.start(0,"collision","existing.wav",punchOutFrame=2);drain.thread.join(1)
    with self.assertRaisesRegex(RuntimeError,"different fileName"):drain.finish()
    self.assertEqual(target.read_bytes(),b"previous");self.assertIsNotNone(drain.spool)
    with self.assertRaises(ValueError):drain.finish("../unsafe.wav")
    receipt=drain.finish("new.wav")
    self.assertEqual(receipt["frames"],2);self.assertTrue((root/"new.wav").exists())
   finally:drain.abort()
 def test_nonempty_tail_fails_instead_of_publishing_unbounded_capture(self):
  with tempfile.TemporaryDirectory() as raw:
   native=FakeCaptureNative();entered=Event();release=Event();sequence=0
   def endless_pop(track):
    nonlocal sequence
    entered.set();release.wait(1);sequence+=1
    return {"sequence":sequence,"showFrame":(sequence-1)*2,"frames":2,"left":[.1,.2],"right":[.1,.2]}
   native.daw_record_pop=endless_pop;drain=CaptureDrainer(native,Path(raw));drain.STOP_TIMEOUT_SECONDS=.02
   try:
    drain.start(0,"endless","endless.wav");self.assertTrue(entered.wait(1))
    with self.assertRaisesRegex(RuntimeError,"take remains pending"):drain.finish()
    release.set();drain.thread.join(1);self.assertFalse(drain.thread.is_alive())
    self.assertEqual(drain.status()["frames"],130)
    with self.assertRaisesRegex(RuntimeError,"bounded tail"):drain.finish()
    self.assertFalse((Path(raw)/"endless.wav").exists())
   finally:release.set();drain.abort()
 def test_capture_failures_disarm_and_block_publication(self):
  for failure in ("disk", "short-channel", "nan", "native"):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as raw:
    native=FakeCaptureNative();drain=CaptureDrainer(native,Path(raw))
    if failure=="short-channel":native.blocks[0]["right"]=[]
    if failure=="nan":native.blocks[0]["left"][0]=float("nan")
    if failure=="native":
     def broken_pop(track):raise RuntimeError("device: empty device response")
     native.daw_record_pop=broken_pop
    original=RecordingSpool.append_s32
    def append(spool,payload,frames):
     if failure=="disk":raise OSError("disk full")
     return original(spool,payload,frames)
    try:
     with patch.object(RecordingSpool,"append_s32",append):
      drain.start(0,"failed","failed.wav");drain.thread.join(1)
     self.assertFalse(drain.thread.is_alive());self.assertFalse(native.armed)
     self.assertEqual(drain.status()["state"],"failed");self.assertTrue(drain.status()["captureError"])
     with self.assertRaisesRegex(RuntimeError,"capture failed"):drain.finish()
     self.assertFalse((Path(raw)/"failed.wav").exists());self.assertIsNotNone(drain.spool)
     drain.abort();self.assertEqual(list(Path(raw).glob("*.wav")),[])
     self.assertEqual(list(Path(raw).glob(".*.partial.wav")),[])
    finally:drain.abort()
 def test_spool_rejects_inconsistent_pcm_without_counting_frames(self):
  with tempfile.TemporaryDirectory() as raw:
   spool=RecordingSpool(Path(raw));spool.begin("shape",acknowledge_physical_input=True)
   try:
    for frames,payload in ((1,b"\0"*4),(-1,b""),(True,b"\0"*8)):
     with self.assertRaises(ValueError):spool.append_s32(payload,frames)
    self.assertEqual(spool.finish("empty.wav")["frames"],0)
   finally:spool.abort()
 def test_stalled_capture_retains_take_until_worker_exits(self):
  for action in ("finish","abort"):
   with self.subTest(action=action),tempfile.TemporaryDirectory() as raw:
    native=FakeCaptureNative();entered=Event();release=Event()
    def blocked_pop(track):
     entered.set();release.wait(2)
     if native.blocks:return native.blocks.pop(0)
     raise RuntimeError("empty: record queue empty")
    native.daw_record_pop=blocked_pop
    drain=CaptureDrainer(native,Path(raw));drain.STOP_TIMEOUT_SECONDS=.02
    try:
     drain.start(0,"pending","take.wav");self.assertTrue(entered.wait(1));worker=drain.thread;spool=drain.spool
     with self.assertRaisesRegex(RuntimeError,"take remains pending"):getattr(drain,action)()
     self.assertIs(drain.spool,spool);self.assertIs(drain.thread,worker)
     self.assertFalse(native.armed);self.assertTrue(drain.status()["stopTimedOut"])
     self.assertFalse((Path(raw)/"take.wav").exists())
     with self.assertRaisesRegex(RuntimeError,"pending capture"):drain.start(0,"new","new.wav")
     release.set();worker.join(1);self.assertFalse(worker.is_alive())
     self.assertEqual(drain.status()["frames"],4 if action=="finish" else 0)
     getattr(drain,action)();self.assertIsNone(drain.spool)
     self.assertEqual((Path(raw)/"take.wav").exists(),action=="finish")
    finally:
     release.set();drain.abort()
 def test_finish_disarms_then_drains_inflight_and_queued_blocks(self):
  with tempfile.TemporaryDirectory() as raw:
   native=FakeCaptureNative();entered=Event();disarmed=Event();pop=native.daw_record_pop
   def waiting_pop(track):
    entered.set()
    if not disarmed.wait(1):raise RuntimeError("test disarm timeout")
    return pop(track)
   def disarm(track):native.armed=False;disarmed.set()
   native.daw_record_pop=waiting_pop;native.daw_record_disarm=disarm
   drain=CaptureDrainer(native,Path(raw))
   try:
    drain.start(0,"tail","tail.wav");self.assertTrue(entered.wait(1))
    receipt=drain.finish()
    self.assertEqual(receipt["frames"],4);self.assertTrue(receipt["queueDrained"])
    self.assertEqual(native.blocks,[]);self.assertFalse(native.armed)
   finally:disarmed.set();drain.abort()
 def test_punch_complete_take_must_be_finalized_before_new_capture(self):
  with tempfile.TemporaryDirectory() as raw:
   drain=CaptureDrainer(FakeCaptureNative(),Path(raw))
   try:
    drain.start(0,"punch","punch.wav",punchOutFrame=2);drain.thread.join(1)
    self.assertFalse(drain.thread.is_alive());self.assertEqual(drain.status()["state"],"punch-complete")
    with self.assertRaisesRegex(RuntimeError,"pending capture"):drain.start(0,"new","new.wav")
    receipt=drain.finish();self.assertEqual(receipt["frames"],2)
    self.assertTrue((Path(raw)/"punch.wav").exists())
   finally:drain.abort()
 def test_drain_writes_atomic_take_and_gap_evidence(self):
  with tempfile.TemporaryDirectory() as raw:
   native=FakeCaptureNative();drain=CaptureDrainer(native,Path(raw));drain.start(0,"take-1","take.wav")
   for _ in range(100):
    if drain.status()["blocks"]==2:break
    time.sleep(.002)
   result=drain.finish();self.assertEqual(result["frames"],4);self.assertEqual(result["dropoutBlocks"],1);self.assertEqual(len(result["dropouts"]),1);self.assertFalse(result["physicalInputArmed"]);self.assertFalse(native.armed);self.assertTrue((Path(raw)/"take.wav").is_file())
if __name__=="__main__":unittest.main()
