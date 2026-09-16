from __future__ import annotations

import math
from typing import Any


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values: return None
    ordered=sorted(values);position=(len(ordered)-1)*fraction;low=math.floor(position);high=math.ceil(position)
    if low==high:return ordered[low]
    return ordered[low]*(high-position)+ordered[high]*(position-low)


def analyze_hardware_samples(samples: list[dict[str, Any]], *, source: str, duration_ms: int,
                             uwb_device: str | None = None, le_controller: str | None = None) -> dict[str, Any]:
    if source not in {"loopback","hardware"}: raise ValueError("source must be loopback or hardware")
    if source=="hardware" and (not uwb_device or not le_controller): raise ValueError("hardware reports require UWB device and LE controller identities")
    valid=[]
    for item in samples:
        try:
            latency=float(item["transportLatencyNs"]);jitter=float(item["jitterNs"]);clock=float(item["clockOffsetNs"])
            sequence=int(item["sequence"])
        except (KeyError,TypeError,ValueError): continue
        if latency<0 or jitter<0 or sequence<1: continue
        valid.append({"transportLatencyNs":latency,"jitterNs":jitter,"clockOffsetNs":clock,"sequence":sequence})
    sequences=sorted({item["sequence"] for item in valid});expected=(sequences[-1]-sequences[0]+1) if sequences else 0;lost=max(0,expected-len(sequences))
    latencies=[item["transportLatencyNs"] for item in valid];jitters=[item["jitterNs"] for item in valid];clocks=[abs(item["clockOffsetNs"]) for item in valid]
    measured=source=="hardware" and bool(valid)
    return {"documentType":"org.upp.hardware-bench-report","schemaVersion":1,"source":source,"measured":measured,
            "durationMs":max(0,int(duration_ms)),"sampleCount":len(valid),"expectedSequences":expected,"lostSequences":lost,
            "packetLossRatio":(lost/expected if expected else None),"transportLatencyNs":{"p50":_percentile(latencies,.5),"p95":_percentile(latencies,.95),"p99":_percentile(latencies,.99),"max":max(latencies) if latencies else None},
            "jitterNs":{"p95":_percentile(jitters,.95),"max":max(jitters) if jitters else None},"absoluteClockOffsetNs":{"p95":_percentile(clocks,.95),"max":max(clocks) if clocks else None},
            "hardware":{"uwbDevice":uwb_device,"leController":le_controller},"physicalOutputsArmed":False,
            "qualification":"measured-hardware" if measured else "simulation-only"}
