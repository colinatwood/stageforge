import sys,time,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from streaming_voice_producer import PolyphonicStreamingProducer
import streaming_voice_producer

class Native:
 def __init__(self):self.available=True;self.blocks=[];self.starts=[];self.stops=[];self.slots={};self.reject_after=None
 def streaming_voice_block(self,slot,generation,sequence,left,right,terminal=False):
  if self.reject_after is not None and len(self.blocks)>=self.reject_after:raise RuntimeError("full")
  self.blocks.append((slot,generation,sequence,len(left),terminal))
 def streaming_voice_start(self,slot,generation,gain=1,loop=False):self.starts.append((slot,generation,gain,loop))
 def streaming_voice_stop(self,slot,generation):self.stops.append((slot,generation))
 def streaming_voice_stop_all(self):self.stops.append(("all",0))
 def streaming_voice_slot_status(self,slot):return self.slots.get(slot,{"generation":"0","active":"0"})

class StreamingVoiceProducerTests(unittest.TestCase):
 def producer(self):
  native=Native();producer=PolyphonicStreamingProducer(native,Path("."));producer.reader=Mock();producer.reader._source_slice.side_effect=lambda uri,start,count:([1.0]*count,[-1.0]*count);return producer,native
 def session(self,frames=600):return {"tracks":[{"clips":[{"clipId":"clip","lengthFrames":frames,"source":{"type":"audio-file","uri":"clip.wav"}}]}]}
 def test_prebuffers_before_start_and_reclaims_exact_completed_generation(self):
  producer,native=self.producer();result=producer.start_clip(self.session(),"clip")
  self.assertEqual([b[3] for b in native.blocks],[256,256,88]);self.assertTrue(native.blocks[-1][4]);self.assertEqual(native.starts,[(0,1,1.0,False)]);self.assertEqual(result["prebufferedBlocks"],3);self.assertTrue(result["independentVoice"])
  native.slots[0]={"generation":"1","active":"0"};self.assertEqual(producer.status()["voices"],[])
 def test_loop_feeder_cancels_during_bounded_backpressure(self):
  producer,native=self.producer();native.reject_after=4;result=producer.start_clip(self.session(256),"clip",loop=True);time.sleep(.01)
  stopped=producer.stop(result["voiceSlot"],result["generation"]);self.assertTrue(stopped["stopQueued"]);self.assertEqual(native.stops,[(0,1)])
 def test_generation_mismatch_cannot_stop_reused_or_other_voice(self):
  producer,_=self.producer();result=producer.start_clip(self.session(1),"clip")
  with self.assertRaises(ValueError):producer.stop(result["voiceSlot"],result["generation"]+1)
  producer.close();self.assertIn(("all",0),producer.native.stops)
 def test_prebuffer_backpressure_times_out_and_releases_reservation(self):
  producer,native=self.producer();native.reject_after=0;previous=streaming_voice_producer.FEED_RETRY_TIMEOUT_SECONDS;streaming_voice_producer.FEED_RETRY_TIMEOUT_SECONDS=.005
  try:
   with self.assertRaisesRegex(RuntimeError,"remained unavailable"):producer.start_clip(self.session(),"clip")
  finally:streaming_voice_producer.FEED_RETRY_TIMEOUT_SECONDS=previous
  self.assertEqual(producer.jobs,{});self.assertEqual(producer.failures,1)

if __name__=="__main__":unittest.main()
