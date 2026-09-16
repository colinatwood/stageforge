import math,struct,sys,tempfile,time,unittest,wave
from pathlib import Path
from threading import Event
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from daw_playback import ArrangementProducer
class FakeNative:
 def __init__(self):self.available=True;self.blocks=[];self.generation=2;self.started=False;self.loop=None
 def daw_playback_seek(self,frame):return {}
 def daw_playback_status(self):return {"generation":str(self.generation),"queuedBlocks":"0"}
 def daw_playback_pcm(self,generation,start,left,right):self.blocks.append((generation,start,left,right));return {}
 def daw_playback_start(self):self.started=True;return {}
 def daw_playback_stop(self):self.started=False;return {}
 def daw_playback_loop(self,begin,end):self.loop=(begin,end);return {}
 def daw_playback_loop_clear(self):self.loop=None;return {}
class DawPlaybackTests(unittest.TestCase):
 def test_arbitrary_loop_block_wraps_sample_exactly_across_multiple_boundaries(self):
  with tempfile.TemporaryDirectory() as raw:
   producer=ArrangementProducer(FakeNative(),Path(raw))
   producer._block=lambda plan,start,frames: ([float(start+i) for i in range(frames)],[-float(start+i) for i in range(frames)])
   left,right=producer._loop_block({},12,8,10,13)
   self.assertEqual(left,[12.0,10.0,11.0,12.0,10.0,11.0,12.0,10.0])
   self.assertEqual(right,[-12.0,-10.0,-11.0,-12.0,-10.0,-11.0,-12.0,-10.0])
   self.assertEqual(producer._advance_loop(12,8,10,13),11)
 def test_clip_loop_uses_exact_clip_length_without_block_rounding(self):
  with tempfile.TemporaryDirectory() as raw:
   producer=ArrangementProducer(FakeNative(),Path(raw));captured={}
   def capture(session,start,end,*,loop=False):
    captured.update(start=start,end=end,loop=loop,session=session);return {"captured":True}
   producer.start=capture
   session={"tracks":[{"trackId":"t","clips":[{"clipId":"c","startFrame":99,"lengthFrames":257,"source":{"type":"generated-silence"}}]}]}
   self.assertEqual(producer.start_clip(session,"c",loop=True),{"captured":True})
   self.assertEqual((captured["start"],captured["end"],captured["loop"]),(0,257,True))
   self.assertEqual(captured["session"]["tracks"][0]["clips"][0]["startFrame"],0)
 def test_blocked_reader_cannot_be_replaced_or_submit_after_cancellation(self):
  with tempfile.TemporaryDirectory() as raw:
   native=FakeNative();producer=ArrangementProducer(native,Path(raw));producer.STOP_TIMEOUT_SECONDS=.02
   entered=Event();release=Event()
   def blocked_read(plan,start,frames):
    entered.set();release.wait(2);return [0.0]*frames,[0.0]*frames
   producer._block=blocked_read
   try:
    producer.start({"tracks":[]},0,256)
    self.assertTrue(entered.wait(1));worker=producer.thread
    with self.assertRaisesRegex(RuntimeError,"restart blocked"):producer.stop()
    self.assertIs(producer.thread,worker)
    self.assertTrue(producer.status()["stopTimedOut"])
    self.assertFalse(native.started)
    with self.assertRaisesRegex(RuntimeError,"restart blocked"):producer.start({"tracks":[]},0,256)
    self.assertIs(producer.thread,worker)
    self.assertTrue(producer.stop_event.is_set())
    release.set();worker.join(1);self.assertFalse(worker.is_alive())
    producer.stop();self.assertEqual(native.blocks,[])
    self.assertFalse(producer.status()["stopTimedOut"])
    producer.start({"tracks":[]},0,256);producer.thread.join(1)
    self.assertEqual(len(native.blocks),1)
   finally:
    release.set();producer.stop()
 def test_real_media_is_prefetched_before_native_submission(self):
  with tempfile.TemporaryDirectory() as raw:
   media=Path(raw);path=media/"tone.wav"
   with wave.open(str(path),"wb") as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b"".join(struct.pack("<h",round(math.sin(i/5)*10000)) for i in range(100)))
   session={"sessionId":"x","revision":1,"tracks":[{"trackId":"t","clips":[{"clipId":"c","startFrame":0,"lengthFrames":256,"source":{"type":"audio-file","uri":"tone.wav"}}]}]};native=FakeNative();producer=ArrangementProducer(native,media);producer.start(session,0,256)
   for _ in range(100):
    if not producer.status()["running"]:break
    time.sleep(.002)
   self.assertEqual(len(native.blocks),1);self.assertEqual(len(native.blocks[0][2]),256);self.assertTrue(native.started);self.assertFalse(producer.status()["physicalOutputsArmed"])
if __name__=="__main__":unittest.main()
