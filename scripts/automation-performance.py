#!/usr/bin/env python3
"""Deterministic automation regression gate with informational timing."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from daw_production import PreparedAutomation,automation_value

class CountingPoint(dict):
    reads=0
    def __getitem__(self,key):type(self).reads+=1;return super().__getitem__(key)

def run_gate(point_count=4096,frames=8192,block_size=256):
    points=[CountingPoint(frame=(i*frames)//point_count,value=((i*37)%101)/100) for i in range(point_count)];CountingPoint.reads=0;started=time.perf_counter();curve=PreparedAutomation(points);prepared_reads=CountingPoint.reads;rendered=[]
    for start in range(0,frames,block_size):rendered.extend(curve.block(start,min(block_size,frames-start)))
    elapsed=time.perf_counter()-started;probes=range(0,frames,max(1,frames//31));equivalent=all(rendered[frame]==automation_value(points,frame,1.0) for frame in probes)
    result={"documentType":"org.upp.automation-performance-report","schemaVersion":1,"points":point_count,"frames":frames,"blockFrames":block_size,"blocks":(frames+block_size-1)//block_size,"preparedPointReads":prepared_reads,"expectedPreparedPointReads":point_count*2,"blockEntrySearch":"binary","equivalentAtProbeFrames":equivalent,"elapsedMilliseconds":round(elapsed*1000,3),"timingIsInformational":True}
    result["passed"]=equivalent and prepared_reads==point_count*2 and len(rendered)==frames;return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--json",action="store_true");args=parser.parse_args();result=run_gate();print(json.dumps(result,sort_keys=True) if args.json else f"Automation gate {'passed' if result['passed'] else 'failed'}: {result['points']} points prepared in {result['preparedPointReads']} reads; {result['frames']} frames in {result['elapsedMilliseconds']} ms");return 0 if result["passed"] else 1
if __name__=="__main__":raise SystemExit(main())
