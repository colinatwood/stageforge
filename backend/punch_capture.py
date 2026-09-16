from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MAX_PRE_ROLL_FRAMES=65_536
MAX_LOOP_PASSES=128

@dataclass(frozen=True)
class CaptureSlice:
    offset:int
    frames:int
    corrected_start_frame:int
    loop_pass:int

class PunchCaptureGate:
    """Generation and frame-window gate; owns no device or file operations."""
    def __init__(self,generation:int,*,punch_in_frame:int=0,punch_out_frame:int|None=None,pre_roll_frames:int=0,
                 latency_compensation_frames:int=0,loop_start_frame:int|None=None,loop_end_frame:int|None=None,maximum_passes:int=1)->None:
        if generation<1:raise ValueError("capture generation must be positive")
        if pre_roll_frames<0 or pre_roll_frames>MAX_PRE_ROLL_FRAMES:raise ValueError("pre-roll exceeds bounded capacity")
        if latency_compensation_frames<0 or latency_compensation_frames>MAX_PRE_ROLL_FRAMES:raise ValueError("latency compensation exceeds bounded capacity")
        if punch_in_frame<0 or (punch_out_frame is not None and punch_out_frame<=punch_in_frame):raise ValueError("invalid punch range")
        looping=loop_start_frame is not None or loop_end_frame is not None
        if looping and (loop_start_frame is None or loop_end_frame is None or loop_start_frame<0 or loop_end_frame<=loop_start_frame):raise ValueError("invalid loop capture range")
        if maximum_passes<1 or maximum_passes>MAX_LOOP_PASSES:raise ValueError("loop capture pass count is out of range")
        self.generation=generation;self.punch_in=punch_in_frame;self.pre_roll=pre_roll_frames;self.latency=latency_compensation_frames
        self.loop_start=loop_start_frame;self.loop_end=loop_end_frame;self.maximum_passes=maximum_passes
        self.capture_start=max(0,punch_in_frame-pre_roll_frames)
        self.capture_end=(loop_start_frame+(loop_end_frame-loop_start_frame)*maximum_passes) if looping else punch_out_frame
        self.selected_frames=0;self.discarded_frames=0;self.stale_blocks=0;self.loop_passes:set[int]=set();self.complete=False

    def select(self,block:dict[str,Any])->list[CaptureSlice]:
        if int(block.get("generation",self.generation))!=self.generation:self.stale_blocks+=1;return []
        frames=int(block.get("frames",0));raw_start=int(block.get("showFrame",0));start=max(0,raw_start-self.latency);end=start+frames
        window_end=self.capture_end if self.capture_end is not None else end
        begin=max(start,self.capture_start);finish=min(end,window_end)
        if finish<=begin:self.discarded_frames+=frames;self.complete=self.capture_end is not None and end>=self.capture_end;return []
        slices=[];cursor=begin
        while cursor<finish:
            loop_pass=0;boundary=finish
            if self.loop_start is not None and self.loop_end is not None:
                if cursor<self.loop_start:boundary=min(finish,self.loop_start)
                else:
                    length=self.loop_end-self.loop_start;loop_pass=(cursor-self.loop_start)//length;boundary=min(finish,self.loop_start+(loop_pass+1)*length);self.loop_passes.add(loop_pass)
            slices.append(CaptureSlice(cursor-start,boundary-cursor,cursor,loop_pass));cursor=boundary
        selected=sum(item.frames for item in slices);self.selected_frames+=selected;self.discarded_frames+=frames-selected
        self.complete=self.capture_end is not None and end>=self.capture_end
        return slices

    def status(self)->dict[str,Any]:
        return {"generation":self.generation,"punchInFrame":self.punch_in,"punchOutFrame":self.capture_end,"captureStartFrame":self.capture_start,
            "preRollFrames":self.pre_roll,"latencyCompensationFrames":self.latency,"loopStartFrame":self.loop_start,"loopEndFrame":self.loop_end,
            "maximumPasses":self.maximum_passes,"completedPasses":len(self.loop_passes),"selectedFrames":self.selected_frames,
            "discardedFrames":self.discarded_frames,"staleBlocks":self.stale_blocks,"punchComplete":self.complete,"frameDomain":"capture-adapter","physicalOutputsArmed":False}
