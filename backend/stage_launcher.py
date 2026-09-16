from __future__ import annotations

from typing import Any


KEYS=("1","2","3","4","5","6","7","8")


def launcher_projection(snapshot:dict[str,Any],sampler:dict[str,Any],capture:dict[str,Any],feedback:dict[str,Any]|None=None)->dict[str,Any]:
    """Build a replaceable UI projection from authoritative runtime state."""
    transport=snapshot.get("transport") or {};assets=sampler.get("assets") or []
    pads=[];seen=set()
    for asset in assets:
        resource=str(asset.get("resourceId","")).strip();mode=str(asset.get("mode","oneshot"))
        if not resource or resource in seen or len(pads)>=len(KEYS):continue
        seen.add(resource);pads.append({"padId":f"sample:{resource}","label":resource,"action":"sample.trigger","resourceId":resource,
            "mode":mode,"shortcut":KEYS[len(pads)],"ready":bool(asset.get("registered")),"midiLearnTarget":"sample.trigger"})
    return {"documentType":"org.upp.stage-launcher","schemaVersion":1,"revision":int(snapshot.get("revision",0)),
        "transport":{"running":bool(transport.get("running",False)),"seconds":float(transport.get("seconds",0)),"bpm":float(transport.get("bpm",120)),"key":str(transport.get("key","C"))},
        "capture":{"state":str(capture.get("state","idle")),"physicalInputArmed":bool(capture.get("physicalInputArmed",False)),"dropoutBlocks":int(capture.get("dropoutBlocks",0))},
        "controls":[{"controlId":"transport-toggle","label":"Play / Pause","action":"transport.toggle","shortcut":"Space"},
            {"controlId":"transport-stop","label":"Stop","action":"transport.stop","shortcut":"Escape"}],
        "pads":pads,"feedback":dict(feedback or {}),"authority":"core","physicalOutputsArmed":False}
