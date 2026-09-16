from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qualification_bundle import validate_result

DOCUMENT_TYPE_REVIEW = "org.upp.external-qualification-review"
SCHEMA_VERSION = 1
_PURPOSE = b"org.upp.external-qualification-review/1\n"
_MAX_KEY_FILE = 8192
_DECISIONS = frozenset({"approve", "reject", "needs-evidence"})


def _canonical(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def document_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("qualification artifact must be a regular file")
        for chunk in iter(lambda: stream.read(65536), b""):
            size += len(chunk)
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
        ):
            raise ValueError("qualification artifact changed while reading")
    return "sha256:" + digest.hexdigest(), size


def _valid_hash(value: str) -> bool:
    value = value.lower()
    return len(value) == 71 and value.startswith("sha256:") and all(ch in "0123456789abcdef" for ch in value[7:])


def load_review_key(path: Path) -> tuple[str, str, bytes]:
    try:
        path = Path(path)
        if not path.is_absolute():
            raise ValueError("absolute path required")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or stat.S_IMODE(before.st_mode) & 0o077 or before.st_size > _MAX_KEY_FILE):
                raise ValueError("invalid review key file")
            data = stream.read(_MAX_KEY_FILE + 1)
            after = os.fstat(stream.fileno())
            if (len(data) > _MAX_KEY_FILE or
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                raise ValueError("review key file changed while reading")
        document = json.loads(data.decode("utf-8"))
        if not isinstance(document, dict) or set(document) != {"version", "keyId", "reviewerIdHash", "secret"}:
            raise ValueError("invalid review key document")
        if document["version"] != 1 or type(document["version"]) is not int:
            raise ValueError("unsupported review key version")
        key_id = str(document["keyId"])
        reviewer_hash = str(document["reviewerIdHash"]).lower()
        secret_text = str(document["secret"])
        if not 1 <= len(key_id) <= 64 or not key_id.isascii() or any(not (ch.isalnum() or ch in "._-") for ch in key_id):
            raise ValueError("invalid review key id")
        if not _valid_hash(reviewer_hash):
            raise ValueError("invalid reviewer identity hash")
        if not 32 <= len(secret_text) <= 512 or not secret_text.isascii() or any(ord(ch) < 33 or ord(ch) > 126 for ch in secret_text):
            raise ValueError("invalid review secret")
        return key_id, reviewer_hash, secret_text.encode("ascii")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, AttributeError, RecursionError):
        raise PermissionError("qualification review key unavailable or invalid") from None


def verify_artifacts(result: dict[str, Any], artifact_root: Path) -> list[dict[str, Any]]:
    root = Path(artifact_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("qualification artifact root must be a directory")
    verified: list[dict[str, Any]] = []
    for item in result.get("artifacts", []):
        relative = str(item["relativePath"])
        try:
            candidate = (root / relative).resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError(f"qualification artifact is unavailable: {item['name']}") from None
        try:
            candidate.relative_to(root)
        except ValueError:
            raise ValueError("qualification artifact escapes artifact root") from None
        if candidate.is_symlink():
            raise ValueError("qualification artifact must not be a symlink")
        digest, size = _sha256_file(candidate)
        if digest != str(item["sha256"]).lower() or size != item["sizeBytes"]:
            raise ValueError(f"qualification artifact digest/size mismatch: {item['name']}")
        verified.append({
            "kind": item["kind"], "name": item["name"], "relativePath": relative,
            "sha256": digest, "sizeBytes": size, "verified": True,
        })
    return verified


def _review_payload(*, plan: dict[str, Any], result: dict[str, Any], verified: list[dict[str, Any]],
                    key_id: str, reviewer_hash: str, decision: str, reviewed_at: str,
                    notes: list[str]) -> dict[str, Any]:
    accepted = validate_result(plan, result)
    if decision not in _DECISIONS:
        raise ValueError("invalid qualification review decision")
    if decision == "approve" and not accepted["passed"]:
        raise ValueError("qualification review cannot approve a non-passing result")
    if len(notes) > 32 or any(not isinstance(note, str) or len(note) > 1024 for note in notes):
        raise ValueError("qualification review notes are not bounded")
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("qualification review requires an offset-aware reviewedAt timestamp") from None
    return {
        "documentType": DOCUMENT_TYPE_REVIEW,
        "schemaVersion": SCHEMA_VERSION,
        "planId": plan["planId"],
        "taskId": accepted["taskId"],
        "build": dict(plan["build"]),
        "resultSha256": document_sha256(result),
        "reviewer": {"keyId": key_id, "reviewerIdHash": reviewer_hash},
        "decision": decision,
        "reviewedAt": reviewed_at,
        "eligibleForBacklogReview": decision == "approve" and accepted["passed"],
        "backlogIds": accepted["backlogIds"],
        "requiredClaims": accepted["requiredClaims"],
        "requiredArtifacts": accepted["requiredArtifacts"],
        "claims": accepted["claims"],
        "artifactVerification": verified,
        "notes": notes,
        "physicalOutputsArmed": False,
    }


def create_review(*, plan: dict[str, Any], result: dict[str, Any], artifact_root: Path,
                  review_key_file: Path, decision: str, reviewed_at: str | None = None,
                  notes: list[str] | None = None) -> dict[str, Any]:
    accepted = validate_result(plan, result)
    if decision == "approve" and not accepted["passed"]:
        raise ValueError("qualification review cannot approve a non-passing result")
    verified = verify_artifacts(result, artifact_root)
    required = next(item for item in plan["tasks"] if item["taskId"] == result["taskId"])["requiredArtifacts"]
    kinds = {item["kind"] for item in verified}
    if result.get("passed") is True and any(kind not in kinds for kind in required):
        raise ValueError("qualification review is missing required verified artifacts")
    key_id, reviewer_hash, secret = load_review_key(review_key_file)
    timestamp = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = _review_payload(plan=plan, result=result, verified=verified, key_id=key_id,
                              reviewer_hash=reviewer_hash, decision=decision,
                              reviewed_at=timestamp, notes=list(notes or []))
    signature = hmac.new(secret, _PURPOSE + _canonical(payload), hashlib.sha256).hexdigest()
    return {**payload, "hmacSha256": signature}


def validate_review(*, plan: dict[str, Any], result: dict[str, Any], review: dict[str, Any],
                    review_key_file: Path) -> dict[str, Any]:
    key_id, reviewer_hash, secret = load_review_key(review_key_file)
    signature = str(review.get("hmacSha256", "")).lower()
    payload = {key: value for key, value in review.items() if key != "hmacSha256"}
    expected = hmac.new(secret, _PURPOSE + _canonical(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise PermissionError("qualification review signature is invalid")
    if review.get("documentType") != DOCUMENT_TYPE_REVIEW or review.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("invalid qualification review document")
    if review.get("planId") != plan.get("planId") or review.get("build") != plan.get("build"):
        raise ValueError("qualification review does not match this exact build plan")
    if review.get("resultSha256") != document_sha256(result):
        raise ValueError("qualification review does not match the reviewed result")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict) or reviewer.get("keyId") != key_id or reviewer.get("reviewerIdHash") != reviewer_hash:
        raise PermissionError("qualification review signer identity is invalid")
    accepted = validate_result(plan, result)
    if review.get("taskId") != accepted["taskId"] or review.get("backlogIds") != accepted["backlogIds"]:
        raise ValueError("qualification review task/backlog binding is invalid")
    if review.get("physicalOutputsArmed") is not False:
        raise ValueError("qualification review must not arm physical outputs")
    decision = review.get("decision")
    eligible = decision == "approve" and accepted["passed"]
    if review.get("eligibleForBacklogReview") is not eligible:
        raise ValueError("qualification review eligibility flag is inconsistent")
    return {"accepted": True, "decision": decision, "eligibleForBacklogReview": eligible,
            "taskId": accepted["taskId"], "backlogIds": accepted["backlogIds"],
            "resultSha256": review["resultSha256"], "reviewerIdHash": reviewer_hash}
