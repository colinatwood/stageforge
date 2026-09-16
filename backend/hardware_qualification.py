from __future__ import annotations
import os,shutil
from pathlib import Path
from typing import Any

CANONICAL_RATE=192000;CANONICAL_FORMAT="float32-planar"

def probe_platform(*, sys_root:Path=Path("/sys"),dev_root:Path=Path("/dev"))->dict[str,Any]:
    bluetooth=list((sys_root/"class/bluetooth").glob("hci*")) if (sys_root/"class/bluetooth").exists() else []
    uwb=list(dev_root.glob("ttyACM*"))+list(dev_root.glob("ttyUSB*")) if dev_root.exists() else []
    sound=list((sys_root/"class/sound").glob("card*")) if (sys_root/"class/sound").exists() else []
    return {"documentType":"org.upp.platform-qualification","schemaVersion":1,
            "canonicalAudio":{"sampleRate":CANONICAL_RATE,"sampleFormat":CANONICAL_FORMAT,"upscalingRestoresMissingBandwidth":False},
            "audio":{"devices":[str(p) for p in sound],"qualified":False},
            "leAudio":{"controllers":[p.name for p in bluetooth],"bluezAvailable":bool(shutil.which("bluetoothctl")),"bapQualified":False},
            "uwb":{"devices":[str(p) for p in uwb],"qualified":False},
            "qualification":"hardware-tests-required","physicalOutputsArmed":False}

def validate_le_uwb_plan(plan:dict[str,Any])->dict[str,Any]:
    interval=int(plan.get("isoIntervalUs",0));presentation=int(plan.get("presentationDelayUs",0));uwb_rate=int(plan.get("uwbUpdateHz",0))
    if interval not in {5000,7500,10000} or presentation<interval or uwb_rate<1 or uwb_rate>200:
        raise ValueError("invalid LE Audio/UWB timing plan")
    return {**plan,"validated":True,"leAudioCarriesProgram":True,"uwbCarriesProgram":False,"physicalOutputsArmed":False}
