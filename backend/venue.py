from __future__ import annotations

from copy import deepcopy
from typing import Any

from compatibility import QUALITY_ORDER, normalize_participant, resolve_requirements

VENUE_PROFILE_DOCUMENT_TYPE = "org.upp.venue-profile"
VENUE_PROFILE_SCHEMA_VERSION = 1


def inspect_venue_profile(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"readable": False, "mode": "invalid", "reason": "venue profile must be an object", "readerSchemaVersion": VENUE_PROFILE_SCHEMA_VERSION}
    document_type = str(data.get("documentType", VENUE_PROFILE_DOCUMENT_TYPE))
    try:
        incoming = max(1, int(data.get("schemaVersion", VENUE_PROFILE_SCHEMA_VERSION)))
    except (TypeError, ValueError):
        incoming = VENUE_PROFILE_SCHEMA_VERSION
    try:
        minimum = max(1, int(data.get("minimumReaderSchemaVersion", 1)))
    except (TypeError, ValueError):
        minimum = incoming
    if document_type != VENUE_PROFILE_DOCUMENT_TYPE:
        return {"readable": False, "mode": "wrong-document-type", "reason": f"unsupported venue document type: {document_type}", "incomingSchemaVersion": incoming, "minimumReaderSchemaVersion": minimum, "readerSchemaVersion": VENUE_PROFILE_SCHEMA_VERSION}
    if minimum > VENUE_PROFILE_SCHEMA_VERSION:
        return {"readable": False, "mode": "reader-too-old", "reason": f"venue profile requires schema reader {minimum}, this core supports {VENUE_PROFILE_SCHEMA_VERSION}", "incomingSchemaVersion": incoming, "minimumReaderSchemaVersion": minimum, "readerSchemaVersion": VENUE_PROFILE_SCHEMA_VERSION}
    return {
        "readable": True,
        "mode": "exact" if incoming == VENUE_PROFILE_SCHEMA_VERSION else ("forward-compatible" if incoming > VENUE_PROFILE_SCHEMA_VERSION else "legacy"),
        "incomingSchemaVersion": incoming,
        "minimumReaderSchemaVersion": minimum,
        "readerSchemaVersion": VENUE_PROFILE_SCHEMA_VERSION,
        "unknownFieldsPreserved": True,
    }


def _capabilities(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _float(value: Any, default: float = 0.0, minimum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


def normalize_latency(data: Any) -> dict[str, Any]:
    raw = dict(data or {}) if isinstance(data, dict) else {}
    return {
        **raw,
        "fixedMs": _float(raw.get("fixedMs"), 0.0, 0.0),
        "jitterMs": _float(raw.get("jitterMs"), 0.0, 0.0),
        "lookaheadMs": _float(raw.get("lookaheadMs"), 0.0, 0.0),
        "timestamped": bool(raw.get("timestamped", False)),
        "clockClass": str(raw.get("clockClass", "local")).strip()[:64] or "local",
    }


def normalize_device(data: Any, index: int = 0) -> dict[str, Any]:
    raw = dict(data or {}) if isinstance(data, dict) else {}
    device_id = str(raw.get("id") or f"device-{index}").strip()[:128] or f"device-{index}"
    status = str(raw.get("status", "expected")).strip().lower()
    if status not in {"expected", "online", "offline", "degraded", "unknown"}:
        status = "unknown"
    return {
        **raw,
        "id": device_id,
        "name": str(raw.get("name") or device_id).strip()[:160] or device_id,
        "kind": str(raw.get("kind", "device")).strip().lower()[:64] or "device",
        "status": status,
        "capabilities": _capabilities(raw.get("capabilities")),
        "latency": normalize_latency(raw.get("latency")),
        "roles": _capabilities(raw.get("roles")),
        "matchIds": _capabilities(raw.get("matchIds") or raw.get("aliases")),
        "optional": bool(raw.get("optional", False)),
    }


def normalize_human(data: Any, index: int = 0) -> dict[str, Any]:
    raw = dict(data or {}) if isinstance(data, dict) else {}
    human_id = str(raw.get("id") or f"human-{index}").strip()[:128] or f"human-{index}"
    return {
        **raw,
        "id": human_id,
        "name": str(raw.get("name") or human_id).strip()[:160] or human_id,
        "available": bool(raw.get("available", True)),
        "capabilities": _capabilities(raw.get("capabilities")),
        "roles": _capabilities(raw.get("roles")),
        "authority": _capabilities(raw.get("authority")),
    }


def normalize_patch(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    result: dict[str, Any] = {}
    for logical_id, raw in data.items():
        if isinstance(raw, dict):
            item = dict(raw)
            target = str(item.get("target", "")).strip()[:160]
            if target:
                item["target"] = target
            result[str(logical_id)] = item
        else:
            result[str(logical_id)] = deepcopy(raw)
    return result


def resolve_lighting_fixture_intent(
    mapping: dict[str, Any],
    fixture_id: str,
    parameter: str,
    normalized_value: float,
) -> dict[str, Any]:
    """Resolve portable fixture intent through an already-active venue mapping.

    The show-facing identity is fixture + semantic parameter. Venue-local DMX
    universe/channel details remain in the patch layer so portable show intent
    does not need to be rewritten for each room.
    """
    if not isinstance(mapping, dict):
        raise ValueError("lighting fixture intent requires an active venue mapping")
    patch = mapping.get("patch") if isinstance(mapping.get("patch"), dict) else mapping
    execution = patch.get("execution") if isinstance(patch.get("execution"), dict) else {}
    fixtures = execution.get("fixtures") if isinstance(execution.get("fixtures"), dict) else {}
    fixture_key = str(fixture_id).strip()[:128]
    parameter_key = str(parameter).strip()[:128]
    if not fixture_key or not parameter_key:
        raise ValueError("lighting fixture intent requires fixtureId and parameter")
    fixture = fixtures.get(fixture_key)
    if not isinstance(fixture, dict):
        raise ValueError(f"lighting fixture is not mapped by the active venue: {fixture_key}")
    try:
        universe = int(fixture.get("universe", 0))
        address = int(fixture.get("address", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("lighting fixture universe/address must be integers") from exc
    if not 0 <= universe < 16 or not 1 <= address <= 512:
        raise ValueError("lighting fixture mapping exceeds the supported 16-universe/512-channel domain")
    parameters = fixture.get("parameters") if isinstance(fixture.get("parameters"), dict) else {}
    spec = parameters.get(parameter_key)
    if spec is None:
        raise ValueError(f"lighting parameter is not mapped for fixture {fixture_key}: {parameter_key}")
    if isinstance(spec, bool):
        raise ValueError("lighting parameter offset must be an integer or object")
    if isinstance(spec, int):
        offset, minimum, maximum, invert = spec, 0, 255, False
    elif isinstance(spec, dict):
        try:
            offset = int(spec.get("offset", 0))
            minimum = int(spec.get("minimum", 0))
            maximum = int(spec.get("maximum", 255))
        except (TypeError, ValueError) as exc:
            raise ValueError("lighting parameter mapping values must be integers") from exc
        invert = bool(spec.get("invert", False))
    else:
        raise ValueError("lighting parameter offset must be an integer or object")
    if offset < 0 or address + offset > 512:
        raise ValueError("lighting parameter mapping exceeds DMX channel 512")
    if not 0 <= minimum <= 255 or not 0 <= maximum <= 255 or maximum < minimum:
        raise ValueError("lighting parameter range must satisfy 0 <= minimum <= maximum <= 255")
    try:
        normalized = float(normalized_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("normalized lighting value must be numeric") from exc
    if not 0.0 <= normalized <= 1.0:
        raise ValueError("normalized lighting value must be between 0 and 1")
    effective = 1.0 - normalized if invert else normalized
    value = int(round(minimum + effective * (maximum - minimum)))
    return {
        "fixtureId": fixture_key,
        "parameter": parameter_key,
        "normalizedValue": normalized,
        "universe": universe,
        "channel": address + offset,
        "value": value,
    }


def normalize_venue_profile(data: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(data or {})
    devices = [normalize_device(item, index) for index, item in enumerate(raw.get("devices") or []) if isinstance(item, dict)]
    humans = [normalize_human(item, index) for index, item in enumerate(raw.get("humans") or []) if isinstance(item, dict)]
    adapters = raw.get("adapters") if isinstance(raw.get("adapters"), list) else []
    return {
        **raw,
        "documentType": str(raw.get("documentType", VENUE_PROFILE_DOCUMENT_TYPE)),
        "schemaVersion": max(1, int(raw.get("schemaVersion", VENUE_PROFILE_SCHEMA_VERSION) or VENUE_PROFILE_SCHEMA_VERSION)),
        "minimumReaderSchemaVersion": max(1, int(raw.get("minimumReaderSchemaVersion", 1) or 1)),
        "unknownFieldsPreserved": bool(raw.get("unknownFieldsPreserved", True)),
        "id": str(raw.get("id", "venue")).strip()[:128] or "venue",
        "name": str(raw.get("name", "Venue")).strip()[:160] or "Venue",
        "capabilities": _capabilities(raw.get("capabilities")),
        "devices": devices,
        "humans": humans,
        "adapters": [dict(item) for item in adapters if isinstance(item, dict)],
        "patch": normalize_patch(raw.get("patch")),
        "clock": normalize_latency(raw.get("clock")),
        "offlineCapable": bool(raw.get("offlineCapable", True)),
        "preservesUnknown": bool(raw.get("preservesUnknown", True)),
    }


def merge_discovered_devices(profile: dict[str, Any], discovered: Any) -> tuple[list[dict[str, Any]], list[str]]:
    expected = {item["id"]: dict(item) for item in profile.get("devices", [])}
    # None means no discovery evidence was supplied. Preserve the venue's
    # expected-state declaration. An explicit [] means discovery ran and found
    # nothing, so expected online devices become offline.
    if discovered is None:
        return sorted([{**item, "discovered": None} for item in expected.values()], key=lambda item: item["id"]), []
    discovered_items = [normalize_device(item, index) for index, item in enumerate(discovered or []) if isinstance(item, dict)]
    discovered_by_id = {item["id"]: item for item in discovered_items}
    merged: list[dict[str, Any]] = []
    warnings: list[str] = []

    for device_id, item in expected.items():
        actual = discovered_by_id.pop(device_id, None)
        if actual is None:
            for alias in item.get("matchIds", []):
                if alias in discovered_by_id:
                    actual = discovered_by_id.pop(alias)
                    break
        if actual is None:
            status = "offline" if item.get("status") in {"online", "expected"} else item.get("status", "offline")
            merged.append({**item, "status": status, "discovered": False})
            if not item.get("optional", False):
                warnings.append(f"expected device offline: {device_id}")
            continue
        capabilities = sorted(set(item.get("capabilities", [])) | set(actual.get("capabilities", [])))
        latency = {**item.get("latency", {}), **actual.get("latency", {})}
        merged.append({**item, **actual, "id": device_id, "discoveredId": actual.get("id"), "capabilities": capabilities, "latency": normalize_latency(latency), "discovered": True})

    for item in discovered_by_id.values():
        merged.append({**item, "discovered": True, "unexpected": True})
        warnings.append(f"unprofiled device discovered: {item['id']}")

    return sorted(merged, key=lambda item: item["id"]), warnings


def venue_participant(profile: dict[str, Any], devices: list[dict[str, Any]]) -> dict[str, Any]:
    capabilities = set(profile.get("capabilities", []))
    for device in devices:
        if device.get("status") in {"online", "expected"}:
            capabilities.update(device.get("capabilities", []))
    for human in profile.get("humans", []):
        if human.get("available"):
            capabilities.update(human.get("capabilities", []))
    return normalize_participant({
        "id": profile.get("id", "venue"),
        "apiVersions": profile.get("apiVersions") or [1],
        "schemaVersions": profile.get("schemaVersions") or {"org.upp.show-state": [1]},
        "capabilities": sorted(capabilities),
        "adapters": profile.get("adapters") or [],
        "preservesUnknown": profile.get("preservesUnknown", True),
        "offlineCapable": profile.get("offlineCapable", True),
    })


def _find_provider(capability: str, devices: list[dict[str, Any]], humans: list[dict[str, Any]]) -> dict[str, Any] | None:
    for device in devices:
        if capability in device.get("capabilities", []) and device.get("status") in {"online", "expected"}:
            return {
                "type": "device",
                "id": device["id"],
                "name": device.get("name", device["id"]),
                "discoveredId": device.get("discoveredId"),
                "discovered": device.get("discovered"),
                "latency": device.get("latency", {}),
            }
    for human in humans:
        if capability in human.get("capabilities", []) and human.get("available"):
            return {"type": "human", "id": human["id"], "name": human.get("name", human["id"]), "authority": human.get("authority", [])}
    return None


def _timing_assessment(requirement: dict[str, Any], provider: dict[str, Any] | None) -> dict[str, Any]:
    timing = requirement.get("timing") if isinstance(requirement.get("timing"), dict) else {}
    if not timing:
        return {"required": False, "status": "not-specified"}
    max_latency = _float(timing.get("maxLatencyMs"), 0.0, 0.0)
    max_jitter = _float(timing.get("maxJitterMs"), 0.0, 0.0)
    require_timestamp = bool(timing.get("timestamped", False))
    if not provider or provider.get("type") != "device":
        return {
            "required": True,
            "status": "human-or-unknown" if provider else "unavailable",
            "maxLatencyMs": max_latency,
            "maxJitterMs": max_jitter,
            "timestampedRequired": require_timestamp,
        }
    latency = provider.get("latency") or {}
    fixed = _float(latency.get("fixedMs"), 0.0, 0.0)
    jitter = _float(latency.get("jitterMs"), 0.0, 0.0)
    timestamped = bool(latency.get("timestamped", False))
    problems: list[str] = []
    if max_latency and fixed > max_latency:
        problems.append(f"latency {fixed:g}ms exceeds {max_latency:g}ms")
    if max_jitter and jitter > max_jitter:
        problems.append(f"jitter {jitter:g}ms exceeds {max_jitter:g}ms")
    if require_timestamp and not timestamped:
        problems.append("timestamped execution unavailable")
    return {
        "required": True,
        "status": "blocked" if problems else "compatible",
        "fixedMs": fixed,
        "jitterMs": jitter,
        "timestamped": timestamped,
        "maxLatencyMs": max_latency,
        "maxJitterMs": max_jitter,
        "timestampedRequired": require_timestamp,
        "problems": problems,
    }


def venue_compatibility_plan(
    profile_data: dict[str, Any],
    requirements: list[dict[str, Any]],
    *,
    discovered_devices: Any = None,
) -> dict[str, Any]:
    profile_report = inspect_venue_profile(profile_data)
    if not profile_report.get("readable"):
        raise ValueError(profile_report.get("reason", "venue profile is not readable by this core"))
    profile = normalize_venue_profile(profile_data)
    devices, discovery_warnings = merge_discovered_devices(profile, discovered_devices)
    participant = venue_participant(profile, devices)
    execution = resolve_requirements(participant, requirements)
    decision_by_id = {item["id"]: item for item in execution.get("requirements", [])}
    device_plan: list[dict[str, Any]] = []
    timing_blockers: list[str] = []
    human_assisted = 0

    for requirement in requirements:
        requirement_id = str(requirement.get("id") or requirement.get("preferred") or "requirement")
        decision = decision_by_id.get(requirement_id, {})
        chosen_capability = str(decision.get("capability") or decision.get("preferred") or "")
        provider = _find_provider(chosen_capability, devices, profile.get("humans", [])) if chosen_capability else None
        timing = _timing_assessment(requirement, provider)
        if timing.get("status") == "blocked" and requirement.get("required", True):
            timing_blockers.append(f"timing blocked: {requirement_id}: " + "; ".join(timing.get("problems", [])))
        if provider and provider.get("type") == "human":
            human_assisted += 1
        patch_key = str(requirement.get("patchKey") or requirement_id)
        patch = profile.get("patch", {}).get(patch_key)
        device_plan.append({
            "id": requirement_id,
            "decision": decision,
            "provider": provider,
            "timing": timing,
            "patch": deepcopy(patch),
            "patchStatus": "mapped" if patch is not None else "unmapped",
        })

    blockers = [
        f"show requirement blocked: {item['id']}"
        for item in execution.get("requirements", [])
        if item.get("status") == "blocked"
    ] + timing_blockers
    required_unmapped = [
        item["id"] for item in device_plan
        if item["decision"].get("required") and item["provider"] and item.get("patchStatus") == "unmapped"
        and str(item["decision"].get("preferred", "")).startswith(("audio.", "lighting.", "midi."))
    ]
    # Missing patch is a preparation issue, not automatically a compatibility
    # blocker. A venue can be capable but not yet patched for this show.
    readiness = "blocked" if blockers else ("needs-patch" if required_unmapped else "ready")
    minimum = int(execution.get("minimumQualityScore", 0))
    if blockers:
        grade = "blocked"
    elif minimum >= 100:
        grade = "direct"
    elif minimum >= 95:
        grade = "equivalent"
    elif minimum >= 80:
        grade = "acceptable"
    else:
        grade = "degraded"

    departments: dict[str, dict[str, Any]] = {}
    actions: list[dict[str, Any]] = []
    requirement_lookup = {str(item.get("id")): item for item in requirements}
    for item in device_plan:
        req = requirement_lookup.get(item["id"], {})
        domain = str(req.get("domain", "other"))
        dept = departments.setdefault(domain, {"domain": domain, "requirements": 0, "blocked": 0, "minimumQualityScore": 100, "humanAssisted": 0})
        dept["requirements"] += 1
        decision = item.get("decision") or {}
        if decision.get("required"):
            dept["minimumQualityScore"] = min(dept["minimumQualityScore"], int(decision.get("qualityScore", 0)))
        if decision.get("status") == "blocked" or item.get("timing", {}).get("status") == "blocked":
            dept["blocked"] += 1
        provider_info = item.get("provider") or {}
        if provider_info.get("type") == "human":
            dept["humanAssisted"] += 1
            actions.append({"type": "confirm-human", "requirement": item["id"], "provider": provider_info.get("id"), "message": f"Confirm human-assisted capability for {item['id']}"})
        if decision.get("status") == "adapter":
            adapter = decision.get("adapter") or {}
            actions.append({"type": "verify-adapter", "requirement": item["id"], "from": adapter.get("from"), "to": adapter.get("to"), "message": f"Verify explicit adapter for {item['id']}"})
        if item.get("patchStatus") == "unmapped" and decision.get("required") and item.get("provider"):
            actions.append({"type": "patch", "requirement": item["id"], "message": f"Patch logical requirement {item['id']} to venue hardware"})
        for problem in item.get("timing", {}).get("problems", []):
            actions.append({"type": "timing", "requirement": item["id"], "message": str(problem)})
    for warning in discovery_warnings:
        actions.append({"type": "discovery", "message": warning})
    for blocker in blockers:
        actions.append({"type": "blocker", "message": blocker})
    for dept in departments.values():
        score = int(dept["minimumQualityScore"])
        dept["grade"] = "blocked" if dept["blocked"] else ("direct" if score >= 100 else "equivalent" if score >= 95 else "acceptable" if score >= 80 else "degraded")

    return {
        "compatible": not blockers,
        "grade": grade,
        "readiness": readiness,
        "venue": {k: deepcopy(v) for k, v in profile.items() if k not in {"devices", "humans", "adapters", "patch"}},
        "profileCompatibility": profile_report,
        "execution": execution,
        "devicePlan": device_plan,
        "departments": sorted(departments.values(), key=lambda item: item["domain"]),
        "actions": actions,
        "devices": devices,
        "humans": profile.get("humans", []),
        "patch": profile.get("patch", {}),
        "humanAssistedRequirements": human_assisted,
        "unmappedRequired": required_unmapped,
        "discoveryWarnings": discovery_warnings,
        "blockers": blockers,
    }

class VenueProfileStore:
    """Small local store for the currently selected venue profile.

    Venue data is intentionally separate from show-state replication. Touring
    show intent remains portable; the venue profile is an environment input.
    """
    def __init__(self, path) -> None:
        from pathlib import Path
        from threading import RLock
        self.path = Path(path)
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        import json
        with self._lock:
            if not self.path.is_file():
                return normalize_venue_profile({"id": "unassigned", "name": "No venue selected"})
            try:
                value = json.loads(self.path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                return normalize_venue_profile({"id": "invalid", "name": "Venue profile unavailable"})
            return normalize_venue_profile(value if isinstance(value, dict) else {})

    def save(self, profile: dict[str, Any]) -> dict[str, Any]:
        import json, os, tempfile
        report = inspect_venue_profile(profile)
        if not report.get("readable"):
            raise ValueError(report.get("reason", "venue profile is not readable by this core"))
        normalized = normalize_venue_profile(profile)
        with self._lock:
            data = json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            fd, temp_name = tempfile.mkstemp(prefix=".venue-profile-", suffix=".json", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, self.path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        return normalized
