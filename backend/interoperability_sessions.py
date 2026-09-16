from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
import secrets
from threading import RLock
from time import time_ns
from typing import Any

from compatibility import compatibility_report
from user_profiles import LAYERS, normalize_user_profile


SESSION_STATES = ("offered", "authenticated", "negotiated", "consented", "active", "expired")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def key_fingerprint(secret: bytes) -> str:
    return "sha256:" + hashlib.sha256(secret).hexdigest()


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, dict[str, Any]] = {}
        self._adapters: list[dict[str, Any]] = []
        self._revision = 0
        self._lock = RLock()

    def register(self, capability: dict[str, Any]) -> dict[str, Any]:
        item = deepcopy(capability)
        name = str(item.get("id", "")).strip()
        version = str(item.get("semanticVersion", "")).strip()
        schema_digest = str(item.get("schemaSha256", "")).lower()
        if not name or "." not in name or not version or len(schema_digest) != 64 or any(ch not in "0123456789abcdef" for ch in schema_digest):
            raise ValueError("capability requires namespaced id, semanticVersion and 64-character schemaSha256")
        item.update({"id": name[:160], "semanticVersion": version[:64], "schemaSha256": schema_digest, "provenance": deepcopy(item.get("provenance") or {}), "unknownFieldsPreserved": True})
        with self._lock:
            self._capabilities[name] = item; self._revision += 1
        return deepcopy(item)

    def register_adapter(self, adapter: dict[str, Any]) -> dict[str, Any]:
        item = deepcopy(adapter); source, target = str(item.get("from", "")).strip(), str(item.get("to", "")).strip()
        quality = int(item.get("quality", 0)); provenance = item.get("provenance")
        if not source or not target or quality < 1 or quality > 100 or not isinstance(provenance, dict) or not provenance:
            raise ValueError("adapter requires from, to, quality 1..100 and provenance")
        item.update({"from": source, "to": target, "quality": quality, "explicit": True, "provenance": deepcopy(provenance)})
        with self._lock:
            self._adapters.append(item); self._revision += 1
        return deepcopy(item)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"revision": self._revision, "capabilities": [deepcopy(self._capabilities[key]) for key in sorted(self._capabilities)], "adapters": deepcopy(self._adapters)}


def project_profile(profile: dict[str, Any]) -> dict[str, Any]:
    source = normalize_user_profile(profile)
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    consent: list[dict[str, Any]] = []

    def rank(item: dict[str, Any]) -> tuple[int, int]:
        layer_rank = LAYERS[item["layer"]]
        if item["namespace"].startswith("org.upp.accessibility"):
            if item["layer"] == "user": layer_rank = 6
            elif item["layer"] == "venue": layer_rank = 2
        return layer_rank, int(item["revision"])

    for item in source["preferences"]:
        identity = (item["namespace"], item["key"]); current = selected.get(identity)
        if current is None or rank(item) > rank(current): selected[identity] = deepcopy(item)
    for identity, chosen in selected.items():
        user_choice = next((item for item in source["preferences"] if (item["namespace"], item["key"]) == identity and item["layer"] == "user"), None)
        if chosen["layer"] in {"role", "venue", "session"} and user_choice and chosen["value"] != user_choice["value"]:
            consent.append({"namespace": identity[0], "key": identity[1], "userValue": user_choice["value"], "proposedValue": chosen["value"], "sourceLayer": chosen["layer"]})
    values = sorted(selected.values(), key=lambda item: (item["namespace"], item["key"]))
    return {"profileId": source["profileId"], "profileRevision": source["revision"], "projectionDigestSha256": digest(values), "values": values, "consentRequired": consent, "safeToApply": not consent, "physicalOutputsArmed": False}


def make_authenticated_offer(local: dict[str, Any], remote_participant_id: str, *, authority_epoch: int, sequence: int,
                             ttl_ms: int, secret: bytes, now_unix_ms: int | None = None, nonce: str | None = None) -> dict[str, Any]:
    if not str(remote_participant_id).strip() or not secret:
        raise ValueError("target participant and authentication secret are required")
    now = int(now_unix_ms if now_unix_ms is not None else time_ns() // 1_000_000)
    ttl = max(1, min(int(ttl_ms), 300_000))
    payload = {"documentType": "org.upp.interoperability-offer", "schemaVersion": 1, "participant": deepcopy(local),
               "targetParticipantId": str(remote_participant_id), "authorityEpoch": max(1, int(authority_epoch)),
               "sequence": max(1, int(sequence)), "nonce": nonce or secrets.token_hex(16), "issuedAtUnixMs": now,
               "expiresAtUnixMs": now + ttl, "authentication": {"scheme": "hmac-sha256", "keyFingerprint": key_fingerprint(secret)}}
    transcript = digest(payload); signature = hmac.new(secret, transcript.encode("ascii"), hashlib.sha256).hexdigest()
    return {**payload, "transcriptSha256": transcript, "authentication": {**payload["authentication"], "signature": signature}}


def verify_authenticated_offer(offer: dict[str, Any], *, expected_target: str, secret: bytes, now_unix_ms: int,
                               minimum_protocol_version: int = 1) -> tuple[bool, str]:
    try:
        auth = dict(offer["authentication"]); supplied_signature = str(auth.pop("signature")); payload = deepcopy(offer)
        payload.pop("transcriptSha256", None); payload["authentication"] = auth
        transcript = digest(payload)
        expected = hmac.new(secret, transcript.encode("ascii"), hashlib.sha256).hexdigest()
        participant = offer["participant"]; offered_versions = [int(value) for value in participant.get("apiVersions", [])]
        if not hmac.compare_digest(transcript, str(offer["transcriptSha256"])) or not hmac.compare_digest(expected, supplied_signature): return False, "transcript authentication failed"
        if auth.get("keyFingerprint") != key_fingerprint(secret): return False, "identity fingerprint mismatch"
        if str(offer["targetParticipantId"]) != str(expected_target): return False, "offer target mismatch"
        if int(offer["issuedAtUnixMs"]) > int(now_unix_ms) or int(offer["expiresAtUnixMs"]) < int(now_unix_ms): return False, "offer expired or not yet valid"
        if not offer.get("nonce") or int(offer["authorityEpoch"]) < 1 or int(offer["sequence"]) < 1: return False, "invalid replay fence"
        if not offered_versions or max(offered_versions) < int(minimum_protocol_version): return False, "protocol downgrade detected"
    except (KeyError, TypeError, ValueError): return False, "malformed authenticated offer"
    return True, "ok"


class InteroperabilitySessionManager:
    def __init__(self, local_participant_id: str) -> None:
        self.local_participant_id = str(local_participant_id); self._sessions: dict[str, dict[str, Any]] = {}; self._last_seen: dict[tuple[str, int], int] = {}; self._lock = RLock()

    def authenticate_and_negotiate(self, offer: dict[str, Any], local: dict[str, Any], registry: CapabilityRegistry, *, secret: bytes, now_unix_ms: int, profile_revision: int, authority_epoch: int) -> dict[str, Any]:
        valid, reason = verify_authenticated_offer(offer, expected_target=self.local_participant_id, secret=secret, now_unix_ms=now_unix_ms)
        if not valid: raise ValueError(reason)
        remote_id = str(offer["participant"].get("id", "remote")); epoch, sequence = int(offer["authorityEpoch"]), int(offer["sequence"]); fence = (remote_id, epoch)
        with self._lock:
            if epoch != int(authority_epoch): raise ValueError("authority epoch changed")
            if sequence <= self._last_seen.get(fence, 0): raise ValueError("replayed interoperability offer")
            self._last_seen[fence] = sequence
            registry_snapshot = registry.snapshot(); local_offer = deepcopy(local); local_offer["adapters"] = registry_snapshot["adapters"]
            plan = compatibility_report(local_offer, offer["participant"])
            selected = plan.get("selectedApiVersion")
            minimum_secure = max(int(local_offer.get("minimumSecureApiVersion", 1)), int(offer["participant"].get("minimumSecureApiVersion", 1)))
            if selected is not None and selected < minimum_secure:
                raise ValueError("protocol downgrade detected")
            session_id = digest({"transcript": offer["transcriptSha256"], "local": self.local_participant_id})[:32]
            state = "negotiated" if plan["compatible"] else "expired"
            session = {"sessionId": session_id, "state": state, "authenticated": True, "reason": "ok" if plan["compatible"] else "incompatible",
                       "transcriptSha256": offer["transcriptSha256"], "plan": plan, "profileRevision": int(profile_revision),
                       "registryRevision": registry_snapshot["revision"], "authorityEpoch": epoch, "expiresAtUnixMs": int(offer["expiresAtUnixMs"]),
                       "consentDigestSha256": None, "physicalOutputsArmed": False}
            self._sessions[session_id] = session; return deepcopy(session)

    def consent(self, session_id: str, projection: dict[str, Any], *, accepted: bool) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session["state"] != "negotiated": raise ValueError("session is not awaiting consent")
            if not accepted: session.update({"state": "expired", "reason": "user declined profile projection"}); return deepcopy(session)
            session.update({"state": "consented", "consentDigestSha256": str(projection["projectionDigestSha256"]), "reason": "consented"}); return deepcopy(session)

    def activate(self, session_id: str, *, now_unix_ms: int, profile_revision: int, registry_revision: int, authority_epoch: int) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session["state"] != "consented": raise ValueError("session is not consented")
            changed = int(now_unix_ms) > session["expiresAtUnixMs"] or int(profile_revision) != session["profileRevision"] or int(registry_revision) != session["registryRevision"] or int(authority_epoch) != session["authorityEpoch"]
            if changed: session.update({"state": "expired", "reason": "negotiated inputs changed"}); return deepcopy(session)
            session.update({"state": "active", "reason": "active", "physicalOutputsArmed": False}); return deepcopy(session)

    def status(self, session_id: str, *, now_unix_ms: int | None = None) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session: raise KeyError(session_id)
            if now_unix_ms is not None and int(now_unix_ms) > session["expiresAtUnixMs"]: session.update({"state": "expired", "reason": "session expired"})
            return deepcopy(session)
