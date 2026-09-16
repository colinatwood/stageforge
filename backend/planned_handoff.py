from __future__ import annotations

import hashlib
import hmac
import json
from time import time_ns
from typing import Any

from cluster_secrets import HmacKeySnapshot


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def make_offer(*, transaction_id: int, source_node_id: str, target_node_id: str,
               source_epoch: int, target_epoch: int, target_show_ns: int,
               allow_degraded_program: bool, secret: bytes, key_id: str | None = None) -> dict[str, Any]:
    if not secret:
        raise RuntimeError("planned handoff requires authenticated replication")
    payload = {
        "protocolVersion": 1,
        "transactionId": int(transaction_id),
        "sourceNodeId": str(source_node_id),
        "targetNodeId": str(target_node_id),
        "sourceEpoch": int(source_epoch),
        "targetEpoch": int(target_epoch),
        "targetShowNs": int(target_show_ns),
        "allowDegradedProgram": bool(allow_degraded_program),
        "issuedAtUnixNs": time_ns(),
    }
    if key_id is not None:
        payload["keyId"] = str(key_id)
    if payload["transactionId"] <= 0 or not payload["sourceNodeId"] or not payload["targetNodeId"]:
        raise ValueError("planned handoff identities are required")
    if payload["targetEpoch"] <= payload["sourceEpoch"] or payload["targetShowNs"] <= 0:
        raise ValueError("planned handoff epoch or Show-Time boundary is invalid")
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    signature = hmac.new(secret, digest.encode("ascii"), hashlib.sha256).hexdigest()
    return {**payload, "digestSha256": digest, "hmacSha256": signature}


def verify_offer(offer: dict[str, Any], *, secret: bytes = b"", keyset: HmacKeySnapshot | None = None, expected_target_node_id: str) -> tuple[bool, str]:
    try:
        payload = {key: offer[key] for key in (
            "protocolVersion", "transactionId", "sourceNodeId", "targetNodeId", "sourceEpoch",
            "targetEpoch", "targetShowNs", "allowDegradedProgram", "issuedAtUnixNs"
        )}
        payload["protocolVersion"] = int(payload["protocolVersion"])
        payload["transactionId"] = int(payload["transactionId"])
        payload["sourceEpoch"] = int(payload["sourceEpoch"])
        payload["targetEpoch"] = int(payload["targetEpoch"])
        payload["targetShowNs"] = int(payload["targetShowNs"])
        payload["issuedAtUnixNs"] = int(payload["issuedAtUnixNs"])
        payload["sourceNodeId"] = str(payload["sourceNodeId"])
        payload["targetNodeId"] = str(payload["targetNodeId"])
        payload["allowDegradedProgram"] = bool(payload["allowDegradedProgram"])
        if "keyId" in offer:
            payload["keyId"] = str(offer["keyId"])
    except (KeyError, TypeError, ValueError):
        return False, "malformed planned handoff offer"
    if payload["protocolVersion"] != 1 or payload["targetNodeId"] != expected_target_node_id:
        return False, "planned handoff target or protocol mismatch"
    if payload["transactionId"] <= 0 or payload["targetEpoch"] <= payload["sourceEpoch"] or payload["targetShowNs"] <= 0:
        return False, "invalid planned handoff fencing facts"
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    if not hmac.compare_digest(digest, str(offer.get("digestSha256", ""))):
        return False, "planned handoff digest mismatch"
    auth_secret = secret
    if keyset is not None:
        try:
            auth_secret = keyset.resolve(offer.get("keyId"))
        except PermissionError as exc:
            return False, str(exc)
    expected = hmac.new(auth_secret, digest.encode("ascii"), hashlib.sha256).hexdigest() if auth_secret else ""
    if not auth_secret or not hmac.compare_digest(expected, str(offer.get("hmacSha256", ""))):
        return False, "planned handoff authentication failed"
    return True, "ok"

def make_ready_receipt(*, offer: dict[str, Any], program_ready: bool,
                       secret: bytes, key_id: str | None = None) -> dict[str, Any]:
    if not secret:
        raise RuntimeError("planned handoff requires authenticated replication")
    payload = {
        "protocolVersion": 1,
        "receiptType": "target-ready",
        "transactionId": int(offer["transactionId"]),
        "sourceNodeId": str(offer["sourceNodeId"]),
        "targetNodeId": str(offer["targetNodeId"]),
        "sourceEpoch": int(offer["sourceEpoch"]),
        "targetEpoch": int(offer["targetEpoch"]),
        "targetShowNs": int(offer["targetShowNs"]),
        "programReady": bool(program_ready),
        "issuedAtUnixNs": time_ns(),
    }
    if key_id is not None:
        payload["keyId"] = str(key_id)
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    return {
        **payload,
        "digestSha256": digest,
        "hmacSha256": hmac.new(secret, digest.encode("ascii"), hashlib.sha256).hexdigest(),
    }


def verify_ready_receipt(receipt: dict[str, Any], *, secret: bytes = b"",
                         keyset: HmacKeySnapshot | None = None,
                         expected_source_node_id: str,
                         offer: dict[str, Any]) -> tuple[bool, str]:
    try:
        payload = {key: receipt[key] for key in (
            "protocolVersion", "receiptType", "transactionId", "sourceNodeId", "targetNodeId",
            "sourceEpoch", "targetEpoch", "targetShowNs", "programReady", "issuedAtUnixNs"
        )}
        if not isinstance(payload["programReady"], bool):
            return False, "malformed planned handoff readiness receipt"
        for key in ("protocolVersion", "transactionId", "sourceEpoch", "targetEpoch",
                    "targetShowNs", "issuedAtUnixNs"):
            payload[key] = int(payload[key])
        for key in ("receiptType", "sourceNodeId", "targetNodeId"):
            payload[key] = str(payload[key])
        if "keyId" in receipt:
            payload["keyId"] = str(receipt["keyId"])
    except (KeyError, TypeError, ValueError):
        return False, "malformed planned handoff readiness receipt"
    if (payload["protocolVersion"] != 1 or payload["receiptType"] != "target-ready" or
            payload["sourceNodeId"] != expected_source_node_id):
        return False, "planned handoff readiness target or protocol mismatch"
    for key in ("transactionId", "sourceNodeId", "targetNodeId", "sourceEpoch",
                "targetEpoch", "targetShowNs"):
        if payload[key] != offer.get(key):
            return False, "planned handoff readiness fencing mismatch"
    if receipt.get("keyId") != offer.get("keyId"):
        return False, "planned handoff readiness key mismatch"
    if payload["issuedAtUnixNs"] < int(offer.get("issuedAtUnixNs", 0)):
        return False, "planned handoff readiness predates offer"
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    if not hmac.compare_digest(digest, str(receipt.get("digestSha256", ""))):
        return False, "planned handoff readiness digest mismatch"
    auth_secret = secret
    if keyset is not None:
        try:
            auth_secret = keyset.resolve(receipt.get("keyId"))
        except PermissionError as exc:
            return False, str(exc)
    expected = hmac.new(auth_secret, digest.encode("ascii"), hashlib.sha256).hexdigest() if auth_secret else ""
    if not auth_secret or not hmac.compare_digest(expected, str(receipt.get("hmacSha256", ""))):
        return False, "planned handoff readiness authentication failed"
    return True, "ok"
