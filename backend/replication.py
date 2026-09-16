from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any

from cluster_secrets import HmacKeySnapshot


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def make_envelope(
    snapshot: dict[str, Any],
    *,
    node_id: str,
    epoch: int,
    sequence: int,
    secret: bytes | None = None,
    execution_telemetry: dict[str, Any] | None = None,
    key_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "protocolVersion": 2 if execution_telemetry is not None else 1,
        "sourceNodeId": node_id,
        "epoch": int(epoch),
        "sequence": int(sequence),
        "revision": int(snapshot.get("revision", 0)),
        "snapshot": snapshot,
    }
    if execution_telemetry is not None:
        payload["executionTelemetry"] = execution_telemetry
    if key_id is not None:
        payload["keyId"] = str(key_id)
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    signature = hmac.new(secret, digest.encode("ascii"), hashlib.sha256).hexdigest() if secret else ""
    return {**payload, "digestSha256": digest, "hmacSha256": signature}


def verify_envelope(
    envelope: dict[str, Any], *, secret: bytes | None = None, keyset: HmacKeySnapshot | None = None
) -> tuple[bool, str]:
    try:
        protocol_version = int(envelope["protocolVersion"])
        payload = {
            "protocolVersion": protocol_version,
            "sourceNodeId": str(envelope["sourceNodeId"]),
            "epoch": int(envelope["epoch"]),
            "sequence": int(envelope["sequence"]),
            "revision": int(envelope["revision"]),
            "snapshot": envelope["snapshot"],
        }
        if protocol_version >= 2:
            telemetry = envelope.get("executionTelemetry", {})
            if not isinstance(telemetry, dict):
                return False, "malformed execution telemetry"
            payload["executionTelemetry"] = telemetry
        if "keyId" in envelope:
            payload["keyId"] = str(envelope["keyId"])
    except (KeyError, TypeError, ValueError):
        return False, "malformed replication envelope"
    if payload["protocolVersion"] not in {1, 2} or not isinstance(payload["snapshot"], dict):
        return False, "unsupported replication envelope"
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    if not hmac.compare_digest(digest, str(envelope.get("digestSha256", ""))):
        return False, "replication digest mismatch"
    auth_secret = secret or b""
    if keyset is not None:
        if not keyset.configured:
            auth_secret = b""
        else:
            try:
                auth_secret = keyset.resolve(envelope.get("keyId"))
            except PermissionError as exc:
                return False, str(exc)
    if auth_secret:
        expected = hmac.new(auth_secret, digest.encode("ascii"), hashlib.sha256).hexdigest()
        supplied = str(envelope.get("hmacSha256", ""))
        if not supplied or not hmac.compare_digest(expected, supplied):
            return False, "replication authentication failed"
    if int(payload["revision"]) != int(payload["snapshot"].get("revision", -1)):
        return False, "replication revision does not match snapshot"
    return True, "ok"


@dataclass(frozen=True)
class ReplicationDecision:
    accepted: bool
    reason: str


class ReplicationTracker:
    """Tracks node execution authority and monotonic replica ordering.

    Replication transports are intentionally outside this class. The same
    envelope can move over localhost HTTP, a venue LAN service, removable
    media, or a future UPP transport without changing show-state semantics.
    """

    def __init__(self, node_id: str, role: str = "primary") -> None:
        role = role.strip().lower()
        if role not in {"primary", "standby"}:
            role = "primary"
        self._lock = RLock()
        self._node_id = node_id.strip()[:64] or "node-local"
        self._role = role
        self._epoch = 1
        self._export_sequence = 0
        self._source_node_id = ""
        self._applied_epoch = 0
        self._applied_sequence = 0
        self._applied_revision = 0
        self._last_applied_at = 0.0

    @property
    def role(self) -> str:
        with self._lock:
            return self._role

    def is_primary(self) -> bool:
        return self.role == "primary"

    def set_role(self, role: str) -> dict[str, Any]:
        role = role.strip().lower()
        if role not in {"primary", "standby"}:
            raise ValueError("node role must be primary or standby")
        with self._lock:
            if role != self._role:
                self._epoch += 1
                self._role = role
                self._export_sequence = 0
            return self.status()

    def promote_with_epoch(self, epoch: int) -> dict[str, Any]:
        """Assume primary authority using an externally fenced lease epoch."""
        epoch = max(1, int(epoch))
        with self._lock:
            self._role = "primary"
            self._epoch = max(self._epoch + 1, epoch)
            self._export_sequence = 0
            return self.status()

    def adopt_epoch(self, epoch: int) -> dict[str, Any]:
        """Advance the authority epoch without changing the current role."""
        epoch = max(1, int(epoch))
        with self._lock:
            if epoch > self._epoch:
                self._epoch = epoch
                self._export_sequence = 0
            return self.status()

    def export(
        self,
        snapshot: dict[str, Any],
        secret: bytes | None = None,
        execution_telemetry: dict[str, Any] | None = None,
        key_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._role != "primary":
                raise RuntimeError("only the primary node can export authoritative replication state")
            self._export_sequence += 1
            return make_envelope(
                snapshot,
                node_id=self._node_id,
                epoch=self._epoch,
                sequence=self._export_sequence,
                secret=secret,
                execution_telemetry=execution_telemetry,
                key_id=key_id,
            )

    def can_apply(self, envelope: dict[str, Any]) -> ReplicationDecision:
        with self._lock:
            if self._role != "standby":
                return ReplicationDecision(False, "replica apply is only allowed while node role is standby")
            try:
                epoch = int(envelope["epoch"])
                sequence = int(envelope["sequence"])
                revision = int(envelope["revision"])
                source = str(envelope["sourceNodeId"])
            except (KeyError, TypeError, ValueError):
                return ReplicationDecision(False, "malformed replication ordering metadata")
            if epoch < self._applied_epoch:
                return ReplicationDecision(False, "stale replication epoch")
            if epoch == self._applied_epoch and source == self._source_node_id and sequence <= self._applied_sequence:
                return ReplicationDecision(False, "stale or duplicate replication sequence")
            if epoch == self._applied_epoch and self._applied_revision and revision < self._applied_revision:
                return ReplicationDecision(False, "replication revision moved backwards")
            return ReplicationDecision(True, "ok")

    def mark_applied(self, envelope: dict[str, Any]) -> None:
        with self._lock:
            self._source_node_id = str(envelope["sourceNodeId"])
            self._applied_epoch = int(envelope["epoch"])
            self._applied_sequence = int(envelope["sequence"])
            self._applied_revision = int(envelope["revision"])
            self._epoch = max(self._epoch, self._applied_epoch)
            self._last_applied_at = monotonic()

    def status(self) -> dict[str, Any]:
        with self._lock:
            age_ms = None
            if self._last_applied_at:
                age_ms = int(max(0.0, monotonic() - self._last_applied_at) * 1000)
            return {
                "nodeId": self._node_id,
                "role": self._role,
                "epoch": self._epoch,
                "sourceNodeId": self._source_node_id or None,
                "lastAppliedEpoch": self._applied_epoch,
                "lastAppliedSequence": self._applied_sequence,
                "lastAppliedRevision": self._applied_revision,
                "replicaAgeMs": age_ms,
            }
