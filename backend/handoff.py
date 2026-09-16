from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any


LIVE_REDUNDANCY_MODES = {"none", "split", "network"}
SOURCE_KINDS = {"track", "plugin", "sequence", "generator", "other"}


DEFAULT_HANDOFF_POLICY: dict[str, Any] = {
    "maxReplicaAgeMs": 2500,
    "maxLocalLagMs": 20.0,
    "requiredPrebufferMs": 250.0,
    "executionStatusFreshMs": 2000,
    "requireProgramCursor": True,
    "requireDuplicatedLiveInputs": True,
    "requireDeclaredDeterministicSources": True,
    "allowAuthorityTransferWhenProgramNotReady": True,
}


def default_live_input_redundancy() -> list[dict[str, Any]]:
    return [
        {"slot": slot, "mode": "none", "ready": False, "sourceId": "", "latencyMs": 0.0}
        for slot in range(4)
    ]


def normalize_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "maxReplicaAgeMs": max(100, min(60000, int(raw.get("maxReplicaAgeMs", DEFAULT_HANDOFF_POLICY["maxReplicaAgeMs"])))),
        "maxLocalLagMs": max(0.0, min(5000.0, float(raw.get("maxLocalLagMs", DEFAULT_HANDOFF_POLICY["maxLocalLagMs"])))),
        "requiredPrebufferMs": max(0.0, min(10000.0, float(raw.get("requiredPrebufferMs", DEFAULT_HANDOFF_POLICY["requiredPrebufferMs"])))),
        "executionStatusFreshMs": max(100, min(60000, int(raw.get("executionStatusFreshMs", DEFAULT_HANDOFF_POLICY["executionStatusFreshMs"])))),
        "requireProgramCursor": bool(raw.get("requireProgramCursor", DEFAULT_HANDOFF_POLICY["requireProgramCursor"])),
        "requireDuplicatedLiveInputs": bool(raw.get("requireDuplicatedLiveInputs", DEFAULT_HANDOFF_POLICY["requireDuplicatedLiveInputs"])),
        "requireDeclaredDeterministicSources": bool(raw.get("requireDeclaredDeterministicSources", DEFAULT_HANDOFF_POLICY["requireDeclaredDeterministicSources"])),
        "allowAuthorityTransferWhenProgramNotReady": bool(raw.get("allowAuthorityTransferWhenProgramNotReady", DEFAULT_HANDOFF_POLICY["allowAuthorityTransferWhenProgramNotReady"])),
    }


def normalize_live_inputs(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result = default_live_input_redundancy()
    if not isinstance(raw, list):
        return result
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            slot = int(item.get("slot", -1))
        except (TypeError, ValueError):
            continue
        if not 0 <= slot < 4:
            continue
        mode = str(item.get("mode", "none")).strip().lower()
        if mode not in LIVE_REDUNDANCY_MODES:
            mode = "none"
        source_id = str(item.get("sourceId", "")).strip()[:96]
        try:
            latency_ms = max(0.0, min(5000.0, float(item.get("latencyMs", 0.0))))
        except (TypeError, ValueError):
            latency_ms = 0.0
        ready = bool(item.get("ready", False)) and mode in {"split", "network"} and bool(source_id)
        result[slot] = {"slot": slot, "mode": mode, "ready": ready, "sourceId": source_id, "latencyMs": latency_ms}
    return result


def normalize_deterministic_sources(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw[:32]:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("id", "")).strip()[:96]
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        kind = str(item.get("kind", "other")).strip().lower()
        if kind not in SOURCE_KINDS:
            kind = "other"
        result.append({
            "id": source_id,
            "kind": kind,
            "required": bool(item.get("required", True)),
            "shadowCapable": bool(item.get("shadowCapable", False)),
            "localAssetReady": bool(item.get("localAssetReady", False)),
            "contentHash": str(item.get("contentHash", "")).strip()[:128],
        })
    return result


class HandoffExecutionRegistry:
    """Ephemeral execution evidence from standby render/feed adapters.

    Nothing here is persisted as show intent. Reports age out and must be
    refreshed by the component actually providing the shadow buffer or
    duplicated live input.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._shadow: dict[str, dict[str, Any]] = {}
        self._live: dict[int, dict[str, Any]] = {}

    def report_shadow(self, source_id: str, *, buffered_until_show_ns: int, content_hash: str = "", healthy: bool = True,
                      start_show_ns: int | None = None, rendered_frames: int = 0) -> dict[str, Any]:
        source_id = str(source_id).strip()[:96]
        if not source_id:
            raise ValueError("shadow source id required")
        until = max(0, int(buffered_until_show_ns))
        start_ns = None if start_show_ns is None else max(0, int(start_show_ns))
        frames = max(0, int(rendered_frames))
        verified = bool(start_ns is not None and until > start_ns and frames > 0 and healthy)
        with self._lock:
            previous = self._shadow.get(source_id)
            discontinuities = int((previous or {}).get("discontinuities", 0))
            contiguous_from = start_ns if verified else None
            if verified and previous and previous.get("executionVerified"):
                previous_until = int(previous.get("bufferedUntilShowNs", 0))
                if start_ns == previous_until:
                    contiguous_from = int(previous.get("contiguousFromShowNs", start_ns))
                    frames += int(previous.get("renderedFrames", 0))
                elif start_ns >= int(previous.get("contiguousFromShowNs", 0)) and until <= previous_until:
                    contiguous_from = int(previous.get("contiguousFromShowNs", start_ns))
                    until = previous_until
                    frames += int(previous.get("renderedFrames", 0))
                else:
                    discontinuities += 1
                    verified = False
            self._shadow[source_id] = {
                "sourceId": source_id,
                "contiguousFromShowNs": contiguous_from,
                "bufferedUntilShowNs": until,
                "contentHash": str(content_hash).strip()[:128],
                "healthy": bool(healthy),
                "renderedFrames": frames,
                "discontinuities": discontinuities,
                "executionVerified": verified,
                "evidenceType": "rendered-block" if verified else "reported-horizon",
                "reportedAt": monotonic(),
            }
            return self.snapshot()

    def report_live(self, slot: int, *, source_id: str, healthy: bool = True, latency_ms: float = 0.0,
                    first_show_ns: int | None = None, last_show_ns: int | None = None, frames: int = 0,
                    sequence: int | None = None) -> dict[str, Any]:
        slot = int(slot)
        if not 0 <= slot < 4:
            raise ValueError("live input slot must be 0..3")
        source_id = str(source_id).strip()[:96]
        if not source_id:
            raise ValueError("live feed source id required")
        first_ns = None if first_show_ns is None else max(0, int(first_show_ns))
        last_ns = None if last_show_ns is None else max(0, int(last_show_ns))
        observed_frames = max(0, int(frames))
        seq = None if sequence is None else max(0, int(sequence))
        verified = bool(healthy and first_ns is not None and last_ns is not None and last_ns > first_ns and observed_frames > 0 and seq is not None)
        with self._lock:
            previous = self._live.get(slot)
            discontinuities = int((previous or {}).get("discontinuities", 0))
            if verified and previous and previous.get("executionVerified"):
                expected_seq = int(previous.get("sequence", -1)) + 1
                previous_last = int(previous.get("lastShowNs", -1))
                if seq == int(previous.get("sequence", -1)) and first_ns >= int(previous.get("firstShowNs", 0)) and last_ns <= previous_last:
                    # Idempotent duplicate report.
                    first_ns = int(previous.get("firstShowNs", first_ns))
                    last_ns = previous_last
                    observed_frames += int(previous.get("observedFrames", 0))
                elif seq == expected_seq and first_ns == previous_last:
                    first_ns = int(previous.get("firstShowNs", first_ns))
                    observed_frames += int(previous.get("observedFrames", 0))
                else:
                    discontinuities += 1
                    verified = False
            self._live[slot] = {
                "slot": slot,
                "sourceId": source_id,
                "healthy": bool(healthy),
                "latencyMs": max(0.0, min(5000.0, float(latency_ms))),
                "firstShowNs": first_ns,
                "lastShowNs": last_ns,
                "observedFrames": observed_frames,
                "sequence": seq,
                "discontinuities": discontinuities,
                "executionVerified": verified,
                "evidenceType": "duplicated-feed-block" if verified else "feed-health-report",
                "reportedAt": monotonic(),
            }
            return self.snapshot()

    def clear(self) -> None:
        with self._lock:
            self._shadow.clear()
            self._live.clear()

    def snapshot(self) -> dict[str, Any]:
        now = monotonic()
        with self._lock:
            shadow = []
            for item in self._shadow.values():
                row = {k: v for k, v in item.items() if k != "reportedAt"}
                row["ageMs"] = int(max(0.0, now - float(item["reportedAt"])) * 1000)
                shadow.append(row)
            live = []
            for item in self._live.values():
                row = {k: v for k, v in item.items() if k != "reportedAt"}
                row["ageMs"] = int(max(0.0, now - float(item["reportedAt"])) * 1000)
                live.append(row)
            return {"shadowSources": sorted(shadow, key=lambda v: v["sourceId"]), "liveInputs": sorted(live, key=lambda v: v["slot"])}


@dataclass(frozen=True)
class HandoffFacts:
    role: str
    replica_age_ms: int | None
    source_node_id: str | None
    source_program_cursor_ns: int
    handoff_target_show_ns: int
    local_show_ns: int | None
    active_live_input_slots: tuple[int, ...]
    source_outputs_active: bool
    transport_running: bool


def evaluate_handoff(
    facts: HandoffFacts,
    *,
    policy: dict[str, Any] | None,
    live_inputs: list[dict[str, Any]] | None,
    deterministic_sources: list[dict[str, Any]] | None,
    execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic, explainable handoff policy evaluation.

    This function intentionally does not arm outputs, acquire authority, or
    advance transport. It turns replicated facts + declared redundancy intent
    into a decision record that other implementations can reproduce.
    """
    policy_n = normalize_policy(policy)
    live_n = normalize_live_inputs(live_inputs)
    sources_n = normalize_deterministic_sources(deterministic_sources)
    execution = execution if isinstance(execution, dict) else {}
    shadow_reports = {str(item.get("sourceId", "")): item for item in (execution.get("shadowSources") or []) if isinstance(item, dict)}
    live_reports = {int(item.get("slot", -1)): item for item in (execution.get("liveInputs") or []) if isinstance(item, dict) and str(item.get("slot", "")).lstrip("-").isdigit()}
    fresh_ms = int(policy_n["executionStatusFreshMs"])

    active_slots = sorted({slot for slot in facts.active_live_input_slots if 0 <= slot < 4})
    live_status: list[dict[str, Any]] = []
    missing_live: list[int] = []
    for slot in active_slots:
        config = live_n[slot]
        duplicated = bool(config["ready"] and config["mode"] in {"split", "network"})
        if not duplicated:
            missing_live.append(slot)
        report = live_reports.get(slot) or {}
        execution_ready = bool(
            duplicated
            and report.get("healthy")
            and report.get("executionVerified")
            and int(report.get("ageMs", fresh_ms + 1)) <= fresh_ms
            and str(report.get("sourceId", "")) == str(config.get("sourceId", ""))
        )
        live_status.append({**config, "active": True, "duplicatedReady": duplicated, "executionReady": execution_ready, "executionAgeMs": report.get("ageMs"), "executionVerified": bool(report.get("executionVerified")), "observedFrames": report.get("observedFrames"), "sequence": report.get("sequence"), "discontinuities": report.get("discontinuities")})

    required_sources = [item for item in sources_n if item["required"]]
    source_status: list[dict[str, Any]] = []
    unready_sources: list[str] = []
    for source in required_sources:
        ready = bool(source["shadowCapable"] and source["localAssetReady"])
        if not ready:
            unready_sources.append(source["id"])
        report = shadow_reports.get(source["id"]) or {}
        hash_ok = not source.get("contentHash") or str(report.get("contentHash", "")) == str(source.get("contentHash", ""))
        execution_fresh = int(report.get("ageMs", fresh_ms + 1)) <= fresh_ms
        required_until = facts.handoff_target_show_ns + int(float(policy_n["requiredPrebufferMs"]) * 1_000_000.0)
        execution_ready = bool(ready and report.get("healthy") and report.get("executionVerified") and execution_fresh and hash_ok and int(report.get("bufferedUntilShowNs", 0)) >= required_until)
        source_status.append({**source, "shadowRenderReady": ready, "executionReady": execution_ready, "executionAgeMs": report.get("ageMs"), "bufferedUntilShowNs": report.get("bufferedUntilShowNs"), "executionVerified": bool(report.get("executionVerified")), "renderedFrames": report.get("renderedFrames"), "discontinuities": report.get("discontinuities")})

    missing_live_execution = [item["slot"] for item in live_status if not item.get("executionReady")]
    unready_source_execution = [item["id"] for item in source_status if not item.get("executionReady")]

    local_lag_ms = None
    if facts.local_show_ns is not None and facts.handoff_target_show_ns > 0:
        local_lag_ms = (facts.handoff_target_show_ns - facts.local_show_ns) / 1_000_000.0

    authority_blockers: list[str] = []
    if facts.role != "standby":
        authority_blockers.append("node is not standby")
    if facts.replica_age_ms is None:
        authority_blockers.append("no replica heartbeat received")
    elif facts.replica_age_ms >= policy_n["maxReplicaAgeMs"]:
        authority_blockers.append("replica heartbeat exceeds handoff policy age")

    program_blockers: list[str] = []
    if facts.source_outputs_active and policy_n["requireProgramCursor"] and facts.source_program_cursor_ns <= 0:
        program_blockers.append("source program cursor is unavailable")
    if local_lag_ms is not None and local_lag_ms > policy_n["maxLocalLagMs"]:
        program_blockers.append("standby show clock trails handoff target beyond policy")

    if active_slots:
        mode = "live-input-state-warm"
        if policy_n["requireDuplicatedLiveInputs"] and missing_live:
            program_blockers.append("active live inputs lack duplicated standby feeds")
        program_logic_ready = not program_blockers
        deterministic_eligible = False
        shadow_render_ready = False
        execution_ready = program_logic_ready and not missing_live_execution
    elif facts.source_outputs_active and facts.transport_running:
        mode = "deterministic-prebuffer-eligible"
        deterministic_eligible = True
        if policy_n["requireDeclaredDeterministicSources"] and not required_sources:
            program_blockers.append("deterministic program sources are not declared")
        if unready_sources:
            program_blockers.append("deterministic sources are not shadow-render ready")
        shadow_render_ready = bool(required_sources) and not unready_sources
        program_logic_ready = not program_blockers
        execution_ready = program_logic_ready and bool(required_sources) and not unready_source_execution
    else:
        mode = "state-warm"
        deterministic_eligible = False
        shadow_render_ready = False
        program_logic_ready = not program_blockers
        execution_ready = program_logic_ready

    authority_ready = not authority_blockers
    if policy_n["allowAuthorityTransferWhenProgramNotReady"]:
        ready_for_authority_transfer = authority_ready
    else:
        ready_for_authority_transfer = authority_ready and program_logic_ready

    if not authority_ready:
        action = "wait-for-authority-readiness"
    elif execution_ready and mode == "live-input-state-warm":
        action = "program-takeover-ready-live-feeds"
    elif execution_ready and mode == "deterministic-prebuffer-eligible":
        action = "program-takeover-ready"
    elif program_logic_ready and mode == "state-warm":
        action = "authority-transfer-ready"
    elif program_logic_ready and mode == "live-input-state-warm":
        action = "authority-transfer-ready-live-feeds"
    elif program_logic_ready and mode == "deterministic-prebuffer-eligible":
        action = "start-shadow-prebuffer"
    else:
        action = "authority-transfer-only" if ready_for_authority_transfer else "hold"

    blockers = authority_blockers + program_blockers
    return {
        "mode": mode,
        "policy": policy_n,
        "authorityReady": authority_ready,
        "programLogicReady": program_logic_ready,
        "executionReady": bool(execution_ready),
        "readyForAuthorityTransfer": ready_for_authority_transfer,
        "readyForProgramTakeover": bool(authority_ready and execution_ready),
        "deterministicPrebufferEligible": deterministic_eligible,
        "shadowRenderReady": shadow_render_ready,
        "prebufferReady": bool(mode == "deterministic-prebuffer-eligible" and execution_ready),
        "recommendedAction": action,
        "authorityBlockers": authority_blockers,
        "programBlockers": program_blockers,
        "reasons": blockers,
        "liveInputs": live_status,
        "missingLiveInputSlots": missing_live,
        "missingLiveInputExecutionSlots": missing_live_execution,
        "deterministicSources": source_status,
        "unreadyDeterministicSourceIds": unready_sources,
        "unreadyDeterministicExecutionSourceIds": unready_source_execution,
        "localLagMs": None if local_lag_ms is None else round(local_lag_ms, 3),
    }
