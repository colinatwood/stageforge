"""Deterministic planning for explicitly classified, latency-safe effect shedding."""
from __future__ import annotations
from typing import Any


def overload_shedding_plan(outputs:list[dict[str,Any]],effects:list[dict[str,Any]],policy_bypassed:list[int]|None=None)->dict[str,Any]:
    levels=[]
    for raw in outputs:
        level=raw.get("overloadLevel",0)
        if isinstance(level,bool) or not isinstance(level,int) or not 0<=level<=2:raise ValueError("overload level must be an integer from 0 through 2")
        levels.append(level)
    level=max(levels,default=0);normalized=[];seen=set()
    for raw in effects:
        if not isinstance(raw,dict):raise ValueError("effect classification must be an object")
        effect_id=raw.get("effectId");slot=raw.get("outputSlot");safety=str(raw.get("safetyClass",""));mode=str(raw.get("bypassMode",""));priority=raw.get("shedPriority",0)
        if isinstance(effect_id,bool) or not isinstance(effect_id,int) or effect_id<=0 or effect_id in seen:raise ValueError("effectId must be a unique positive integer")
        if isinstance(slot,bool) or not isinstance(slot,int) or not 0<=slot<=3:raise ValueError("effect outputSlot must be 0..3")
        if safety not in {"essential","optional"}:raise ValueError("effect safetyClass must be essential or optional")
        if mode not in {"never","latency-preserving"}:raise ValueError("effect bypassMode must be never or latency-preserving")
        if isinstance(priority,bool) or not isinstance(priority,int) or not 0<=priority<=1000:raise ValueError("shedPriority must be an integer from 0 through 1000")
        seen.add(effect_id);normalized.append({"effectId":effect_id,"outputSlot":slot,"safetyClass":safety,"bypassMode":mode,"shedPriority":priority})
    eligible=sorted((item for item in normalized if item["safetyClass"]=="optional" and item["bypassMode"]=="latency-preserving"),key=lambda item:(-item["shedPriority"],item["outputSlot"],item["effectId"]))
    blocked=[item["effectId"] for item in normalized if item["safetyClass"]=="optional" and item["bypassMode"]!="latency-preserving"]
    prior=[]
    for value in policy_bypassed or []:
        if isinstance(value,bool) or not isinstance(value,int) or value not in seen:raise ValueError("policyBypassedEffectIds must reference classified effects")
        if value not in prior:prior.append(value)
    bypass=[] if level==0 else ([eligible[0]["effectId"]] if level==1 and eligible else [item["effectId"] for item in eligible])
    restore=sorted(prior) if level==0 else []
    return {"documentType":"org.upp.audio.overload-shedding-plan","schemaVersion":1,"overloadLevel":level,"action":"restore" if restore else ("shed" if bypass else "hold"),"recommendedBypassEffectIds":bypass,"recommendedRestoreEffectIds":restore,"blockedOptionalEffectIds":blocked,"essentialEffectIds":[item["effectId"] for item in normalized if item["safetyClass"]=="essential"],"deterministicOrder":"priority-descending-output-slot-effect-id","requiresPreparedDelayGraph":bool(bypass or restore),"automaticApply":False,"latencyPreservingOnly":True,"physicalOutputsArmed":False}
