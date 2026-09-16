from __future__ import annotations

from typing import Any

MAX_U64 = (1 << 64) - 1


def _u64(value: Any, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 0 or parsed > MAX_U64:
        raise ValueError(f"{name} must be between 0 and {MAX_U64}")
    return parsed


def timing_plan(data: dict[str, Any]) -> dict[str, Any]:
    now_ns = _u64(data.get("nowNs", 0), "nowNs")
    target_ns = _u64(data.get("targetNs"), "targetNs")
    fixed_ns = _u64(data.get("fixedLatencyNs", 0), "fixedLatencyNs")
    jitter_ns = _u64(data.get("jitterNs", 0), "jitterNs")
    lookahead_ns = _u64(data.get("minimumLookaheadNs", 0), "minimumLookaheadNs")
    margin = int(data.get("jitterMarginMultiplier", 2))
    if margin < 0 or margin > 16:
        raise ValueError("jitterMarginMultiplier must be between 0 and 16")
    timestamped = bool(data.get("timestamped", True))
    jitter_margin = min(MAX_U64, jitter_ns * margin)
    path_requirement = min(MAX_U64, fixed_ns + jitter_margin)
    reserve = max(path_requirement, lookahead_ns)
    dispatch = target_ns - reserve if target_ns > reserve else 0
    return {
        "nowNs": now_ns,
        "targetNs": target_ns,
        "dispatchNs": dispatch,
        "reserveNs": reserve,
        "late": now_ns > dispatch,
        "timestamped": timestamped,
        "profile": {
            "fixedLatencyNs": fixed_ns,
            "jitterNs": jitter_ns,
            "minimumLookaheadNs": lookahead_ns,
            "jitterMarginMultiplier": margin,
        },
    }
