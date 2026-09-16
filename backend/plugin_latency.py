from __future__ import annotations
from typing import Any
def latency_compensation_plan(paths:list[dict[str,Any]],*,maximum_delay_frames:int=65536)->dict[str,Any]:
    if not paths:raise ValueError("latency plan requires at least one path")
    if len(paths)>64:raise ValueError("latency plan supports at most 64 paths")
    normalized=[];maximum=0;seen=set();seen_slots=set()
    for raw in paths:
        if not isinstance(raw,dict):raise ValueError("plugin path must be an object")
        latency=raw.get("latencyFrames",0)
        if isinstance(latency,bool) or not isinstance(latency,int):raise ValueError("plugin latency must be an integer frame count")
        if latency<0 or latency>maximum_delay_frames:raise ValueError("plugin path latency exceeds compensation capacity")
        path_id=raw.get("pathId","")
        if not isinstance(path_id,str) or not path_id.strip() or len(path_id)>128:raise ValueError("plugin path id must contain 1..128 characters")
        if path_id in seen:raise ValueError("duplicate plugin path id")
        seen.add(path_id)
        item={"pathId":path_id,"latencyFrames":latency}
        if "outputSlot" in raw:
            slot=raw["outputSlot"]
            if isinstance(slot,bool) or not isinstance(slot,int) or not 0<=slot<=15:raise ValueError("plugin output slot must be an integer from 0 through 15")
            if slot in seen_slots:raise ValueError("duplicate plugin output slot")
            seen_slots.add(slot);item["outputSlot"]=slot
        normalized.append(item);maximum=max(maximum,latency)
    for item in normalized:item["compensationFrames"]=maximum-item["latencyFrames"]
    return {"documentType":"org.upp.daw.plugin-delay-plan","schemaVersion":1,"paths":normalized,"maximumLatencyFrames":maximum,"latencyAligned":True,"physicalOutputsArmed":False}
