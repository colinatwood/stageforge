import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from daw_production import PreparedAutomation, automation_block, automation_value


class AutomationBlockTests(unittest.TestCase):
    def test_matches_scalar_at_boundaries_and_across_blocks(self):
        rng=random.Random(731)
        for size in (0,1,2,40):
            frames=sorted(rng.sample(range(700),size))
            points=[{'frame':frame,'value':rng.random()*2} for frame in frames]
            rng.shuffle(points)
            expected=[automation_value(points,f,1.0) for f in range(800)]
            self.assertEqual(list(automation_block(points,0,800)),expected)
            combined=[]
            for start in range(0,800,256):
                combined.extend(automation_block(points,start,min(256,800-start)))
            self.assertEqual(combined,expected)

    def test_point_data_is_read_once_per_block(self):
        class CountingPoint(dict):
            reads=0
            def __getitem__(self,key):
                type(self).reads+=1
                return super().__getitem__(key)
        points=[CountingPoint(frame=i*10,value=i/4096) for i in range(4096)]
        result=list(automation_block(points,20000,1024))
        self.assertEqual(len(result),1024)
        self.assertEqual(CountingPoint.reads,8192)

    def test_prepared_lane_is_read_once_across_many_blocks(self):
        class CountingPoint(dict):
            reads=0
            def __getitem__(self,key):
                type(self).reads+=1
                return super().__getitem__(key)
        points=[CountingPoint(frame=i*8,value=(i%10)/10) for i in range(4096)]
        CountingPoint.reads=0;curve=PreparedAutomation(points);prepared_reads=CountingPoint.reads;result=[]
        for start in range(0,8192,256):result.extend(curve.block(start,256))
        self.assertEqual(len(result),8192)
        self.assertEqual(prepared_reads,8192)
        self.assertEqual(CountingPoint.reads,8192)

    def test_indexed_entry_preserves_duplicate_and_late_block_semantics(self):
        points=[{"frame":10,"value":.2},{"frame":10,"value":.7},{"frame":1_000_000,"value":.9}]
        curve=PreparedAutomation(points)
        for start in (9,10,11,999_999,1_000_000):
            self.assertEqual(list(curve.block(start,3)),[automation_value(points,frame,1.0) for frame in range(start,start+3)])
