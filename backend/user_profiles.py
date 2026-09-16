from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from threading import RLock
import tempfile
from typing import Any


DOCUMENT_TYPE = "org.upp.user-profile"
SCHEMA_VERSION = 1
LAYERS = {"base": 0, "user": 1, "role": 2, "venue": 3, "session": 4}
VALUE_TYPES = {"boolean", "integer", "scalar", "token"}


def inspect_user_profile(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {"readable": False, "mode": "invalid", "reason": "user profile must be an object"}
    if str(profile.get("documentType", DOCUMENT_TYPE)) != DOCUMENT_TYPE:
        return {"readable": False, "mode": "wrong-document-type", "reason": "unsupported user-profile document type"}
    try:
        incoming = int(profile.get("schemaVersion", 1))
        minimum = int(profile.get("minimumReaderSchemaVersion", incoming))
    except (TypeError, ValueError):
        return {"readable": False, "mode": "invalid", "reason": "profile schema versions must be integers"}
    if minimum > SCHEMA_VERSION:
        return {"readable": False, "mode": "reader-too-old", "reason": f"profile requires reader schema {minimum}", "incomingSchemaVersion": incoming}
    return {"readable": True, "mode": "exact" if incoming == SCHEMA_VERSION else "forward-compatible", "incomingSchemaVersion": incoming, "readerSchemaVersion": SCHEMA_VERSION, "preserveUnknown": True}


def normalize_user_profile(profile: dict[str, Any]) -> dict[str, Any]:
    report = inspect_user_profile(profile)
    if not report.get("readable"):
        raise ValueError(report.get("reason", "user profile is unreadable"))
    result = deepcopy(profile)
    result.update({
        "documentType": DOCUMENT_TYPE,
        "profileId": str(profile.get("profileId", "default")).strip()[:128] or "default",
        "revision": max(0, int(profile.get("revision", 0))),
        "unknownFieldsPreserved": True,
    })
    result.setdefault("schemaVersion", SCHEMA_VERSION)
    result.setdefault("minimumReaderSchemaVersion", 1)
    preferences = profile.get("preferences") or []
    if not isinstance(preferences, list) or len(preferences) > 128:
        raise ValueError("preferences must be an array of at most 128 entries")
    normalized: list[dict[str, Any]] = []
    for raw in preferences:
        if not isinstance(raw, dict):
            raise ValueError("each preference must be an object")
        item = deepcopy(raw)
        namespace, key = str(raw.get("namespace", "")).strip(), str(raw.get("key", "")).strip()
        layer, value_type = str(raw.get("layer", "user")), str(raw.get("type", "token"))
        revision = int(raw.get("revision", 0))
        if not namespace or not key or layer not in LAYERS or value_type not in VALUE_TYPES or revision < 1:
            raise ValueError("invalid preference identity, layer, type, or revision")
        value = raw.get("value")
        if value_type == "boolean" and not isinstance(value, bool):
            raise ValueError("boolean preference requires a boolean value")
        if value_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError("integer preference requires an integer value")
        if value_type == "scalar" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise ValueError("scalar preference requires a numeric value")
        if value_type == "token" and not isinstance(value, str):
            raise ValueError("token preference requires a string value")
        item.update({"namespace": namespace[:128], "key": key[:128], "layer": layer, "type": value_type, "revision": revision, "value": value})
        normalized.append(item)
    result["preferences"] = normalized
    return result


def resolve_user_preferences(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_user_profile(profile)
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for item in normalized["preferences"]:
        identity = (item["namespace"], item["key"])
        current = selected.get(identity)
        if current is None or (LAYERS[item["layer"]], item["revision"]) > (LAYERS[current["layer"]], current["revision"]):
            selected[identity] = deepcopy(item)
    return {"profileId": normalized["profileId"], "revision": normalized["revision"], "resolved": sorted(selected.values(), key=lambda item: (item["namespace"], item["key"])), "physicalOutputsArmed": False}


class UserProfileStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.is_file():
                return normalize_user_profile({"profileId": "default", "preferences": []})
            try:
                value = json.loads(self.path.read_text("utf-8"))
                return normalize_user_profile(value)
            except (OSError, json.JSONDecodeError, ValueError, TypeError):
                return normalize_user_profile({"profileId": "unavailable", "preferences": [], "loadError": True})

    def save(self, profile: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_user_profile(profile)
        with self._lock:
            current = self.load()
            if normalized["revision"] <= current["revision"]:
                raise ValueError("user profile revision must advance")
            data = json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            fd, temporary = tempfile.mkstemp(prefix=".user-profile-", suffix=".json", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(data); handle.flush(); os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
        return normalized
