from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
from pathlib import Path
from threading import RLock
from time import time_ns
from typing import Any
from uuid import uuid4

_ZERO = "0" * 64
_MAX_POLICY_BYTES = 32768
_MAX_WITNESSES = 16


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _record_signature(record_hash: str, signer_id: str, secret: bytes) -> str:
    payload = {"purpose": "org.upp.public-record-signature/1", "recordHash": record_hash, "signerId": signer_id}
    return hmac.new(secret, _canonical(payload), hashlib.sha256).hexdigest()


def make_witness_attestation(record_hash: str, witness_id: str, secret: bytes, *, issued_at_ns: int | None = None) -> dict[str, Any]:
    if len(record_hash) != 64 or any(ch not in "0123456789abcdef" for ch in record_hash):
        raise ValueError("invalid public-record hash")
    witness_id = str(witness_id).strip()
    if not witness_id or len(witness_id) > 64:
        raise ValueError("invalid witness id")
    payload = {
        "version": 1,
        "witnessId": witness_id,
        "recordHash": record_hash,
        "issuedAtNs": int(time_ns() if issued_at_ns is None else issued_at_ns),
    }
    payload["hmacSha256"] = hmac.new(
        secret,
        _canonical({"purpose": "org.upp.public-record-witness/1", "payload": payload}),
        hashlib.sha256,
    ).hexdigest()
    return payload


class PublicRecordStore:
    """Append-only signed operational record plus independently submitted witness attestations.

    Local signatures authenticate records to the node identity key. Optional witness
    attestations are produced outside this store with separately configured witness
    secrets, then verified and persisted as a second hash-linked ledger.
    """

    def __init__(self, path: Path, *, signer_id: str, signing_secret: bytes,
                 witness_policy_path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path)
        self.witness_path = self.path.with_name(self.path.stem + "-witnesses.jsonl")
        self.signer_id = str(signer_id).strip()[:64]
        self.signing_secret = bytes(signing_secret)
        raw_policy = str(witness_policy_path or "").strip()
        self.witness_policy_path = Path(raw_policy) if raw_policy else None
        if not self.signer_id or len(self.signing_secret) < 32:
            raise ValueError("public record signer identity and secret are required")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if self.witness_policy_path is not None:
            self._witness_policy()

    @staticmethod
    def _read_private(path: Path) -> bytes:
        try:
            if not path.is_absolute():
                raise ValueError("absolute path required")
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                        or stat.S_IMODE(before.st_mode) & 0o077 or before.st_size > _MAX_POLICY_BYTES):
                    raise ValueError("invalid witness policy")
                data = stream.read(_MAX_POLICY_BYTES + 1)
                after = os.fstat(stream.fileno())
                if (len(data) > _MAX_POLICY_BYTES
                        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                    raise ValueError("witness policy changed while reading")
            return data
        except (OSError, ValueError):
            raise PermissionError("public-record witness policy unavailable or invalid") from None

    def _witness_policy(self) -> dict[str, Any]:
        if self.witness_policy_path is None:
            return {"quorum": 0, "witnesses": {}}
        try:
            value = json.loads(self._read_private(self.witness_policy_path).decode("utf-8"))
            if not isinstance(value, dict) or set(value) != {"version", "quorum", "witnesses"} or value.get("version") != 1:
                raise ValueError
            witnesses = value.get("witnesses")
            quorum = value.get("quorum")
            if (type(quorum) is not int or not isinstance(witnesses, dict)
                    or not 1 <= len(witnesses) <= _MAX_WITNESSES or not 1 <= quorum <= len(witnesses)):
                raise ValueError
            normalized: dict[str, bytes] = {}
            for witness_id, secret in witnesses.items():
                if (not isinstance(witness_id, str) or not 1 <= len(witness_id) <= 64
                        or not witness_id.isascii() or any(not (c.isalnum() or c in "._-") for c in witness_id)
                        or not isinstance(secret, str) or not 32 <= len(secret) <= 512
                        or not secret.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in secret)):
                    raise ValueError
                normalized[witness_id] = secret.encode("utf-8")
            return {"quorum": quorum, "witnesses": normalized}
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, AttributeError, RecursionError):
            raise PermissionError("public-record witness policy unavailable or invalid") from None

    @staticmethod
    def _last_hash(path: Path) -> str:
        if not path.is_file():
            return _ZERO
        last = ""
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        if not last:
            return _ZERO
        try:
            return str(json.loads(last)["hash"])
        except (json.JSONDecodeError, KeyError, TypeError):
            return "INVALID"

    @staticmethod
    def _append_line(path: Path, value: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def append(self, record_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        record_type = str(record_type).strip()[:96]
        if not record_type or not isinstance(payload, dict):
            raise ValueError("public record requires record type and object payload")
        with self._lock:
            previous = self._last_hash(self.path)
            if previous == "INVALID":
                raise OSError("public record chain is invalid")
            sequence = 1
            if self.path.is_file():
                try:
                    with self.path.open("rb") as handle:
                        sequence = sum(1 for line in handle if line.strip()) + 1
                except OSError:
                    raise OSError("public record unavailable") from None
            core = {
                "sequence": sequence,
                "recordId": "record-" + uuid4().hex[:20],
                "recordType": record_type,
                "timestampNs": time_ns(),
                "payload": payload,
                "previousHash": previous,
            }
            digest = hashlib.sha256(previous.encode("ascii") + b"\n" + _canonical(core)).hexdigest()
            record = {
                **core,
                "hash": digest,
                "signerId": self.signer_id,
                "signatureAlgorithm": "hmac-sha256",
                "signatureHmacSha256": _record_signature(digest, self.signer_id, self.signing_secret),
            }
            self._append_line(self.path, record)
            return {
                "recordId": record["recordId"], "sequence": sequence, "recordHash": digest,
                "signerId": self.signer_id, "signatureAlgorithm": "hmac-sha256",
                "signatureHmacSha256": record["signatureHmacSha256"],
            }

    @staticmethod
    def reference_uri(reference: dict[str, Any]) -> str:
        try:
            record_id = str(reference["recordId"])
            record_hash = str(reference["recordHash"])
        except (KeyError, TypeError):
            raise ValueError("invalid public-record reference") from None
        if (not record_id.startswith("record-") or len(record_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in record_hash)):
            raise ValueError("invalid public-record reference")
        return f"upp-public-record:{record_id}:{record_hash}"

    def resolve_reference(self, uri: str, *, record_type: str | None = None) -> dict[str, Any]:
        """Resolve one signed record by stable URI after verifying the whole chain.

        A reference is never trusted merely because its shape looks plausible. The
        local signed chain must verify first, then both record id and exact hash must
        match. This is control-plane I/O and is intentionally not used on real-time
        execution paths.
        """
        raw = str(uri).strip()
        parts = raw.split(":", 2)
        if len(parts) != 3 or parts[0] != "upp-public-record":
            raise ValueError("invalid public-record reference URI")
        record_id, record_hash = parts[1], parts[2]
        if (not record_id.startswith("record-") or len(record_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in record_hash)):
            raise ValueError("invalid public-record reference URI")
        status = self.verify()
        if not status.get("ok"):
            raise OSError("public record verification failed")
        with self._lock:
            if not self.path.is_file():
                raise KeyError("public-record reference not found")
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        if record.get("recordId") != record_id or record.get("hash") != record_hash:
                            continue
                        if record_type is not None and record.get("recordType") != record_type:
                            raise ValueError("public-record reference has unexpected record type")
                        return record
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                raise OSError("public record unavailable") from None
        raise KeyError("public-record reference not found")

    def _record_hashes(self) -> set[str]:
        hashes: set[str] = set()
        if not self.path.is_file():
            return hashes
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    hashes.add(str(json.loads(line).get("hash", "")))
        return hashes

    def attest(self, attestation: dict[str, Any]) -> dict[str, Any]:
        policy = self._witness_policy()
        if not policy["witnesses"]:
            raise PermissionError("public-record external witnesses are not configured")
        try:
            witness_id = str(attestation["witnessId"])
            record_hash = str(attestation["recordHash"])
            issued_at_ns = int(attestation["issuedAtNs"])
            supplied = str(attestation["hmacSha256"])
        except (KeyError, TypeError, ValueError):
            raise PermissionError("invalid public-record witness attestation") from None
        secret = policy["witnesses"].get(witness_id)
        if secret is None:
            raise PermissionError("unknown public-record witness")
        payload = {"version": 1, "witnessId": witness_id, "recordHash": record_hash, "issuedAtNs": issued_at_ns}
        expected = hmac.new(secret, _canonical({"purpose": "org.upp.public-record-witness/1", "payload": payload}), hashlib.sha256).hexdigest()
        if not supplied or not hmac.compare_digest(expected, supplied):
            raise PermissionError("public-record witness authentication failed")
        with self._lock:
            if record_hash not in self._record_hashes():
                raise ValueError("public-record witness references an unknown record")
            # Exact witness/record replay is idempotent.
            if self.witness_path.is_file():
                with self.witness_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        event = row.get("event") or {}
                        if event.get("witnessId") == witness_id and event.get("recordHash") == record_hash:
                            return {**event, "accepted": True, "deduplicated": True}
            previous = self._last_hash(self.witness_path)
            event = {**payload, "hmacSha256": supplied}
            row = {"event": event, "previousHash": previous}
            row["hash"] = hashlib.sha256(previous.encode("ascii") + b"\n" + _canonical(event)).hexdigest()
            self._append_line(self.witness_path, row)
            return {**event, "accepted": True, "deduplicated": False}

    def verify(self) -> dict[str, Any]:
        with self._lock:
            previous = _ZERO
            records = 0
            record_hashes: set[str] = set()
            if self.path.is_file():
                try:
                    with self.path.open("r", encoding="utf-8") as handle:
                        for line_number, line in enumerate(handle, 1):
                            if not line.strip():
                                continue
                            record = json.loads(line)
                            core = {key: record[key] for key in ("sequence", "recordId", "recordType", "timestampNs", "payload", "previousHash")}
                            if core["previousHash"] != previous or core["sequence"] != records + 1:
                                return {"ok": False, "records": records, "line": line_number, "error": "record chain mismatch"}
                            digest = hashlib.sha256(previous.encode("ascii") + b"\n" + _canonical(core)).hexdigest()
                            if record.get("hash") != digest:
                                return {"ok": False, "records": records, "line": line_number, "error": "record hash mismatch"}
                            expected_sig = _record_signature(digest, str(record.get("signerId", "")), self.signing_secret)
                            if (record.get("signerId") != self.signer_id
                                    or record.get("signatureAlgorithm") != "hmac-sha256"
                                    or not hmac.compare_digest(expected_sig, str(record.get("signatureHmacSha256", "")))):
                                return {"ok": False, "records": records, "line": line_number, "error": "record signature mismatch"}
                            previous = digest
                            record_hashes.add(digest)
                            records += 1
                except (OSError, json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError) as exc:
                    return {"ok": False, "records": records, "error": str(exc)}
            policy = self._witness_policy()
            witness_counts: dict[str, set[str]] = {digest: set() for digest in record_hashes}
            witness_records = 0
            witness_previous = _ZERO
            if self.witness_path.is_file():
                try:
                    with self.witness_path.open("r", encoding="utf-8") as handle:
                        for line_number, line in enumerate(handle, 1):
                            if not line.strip():
                                continue
                            row = json.loads(line); event = row["event"]
                            expected_row = hashlib.sha256(witness_previous.encode("ascii") + b"\n" + _canonical(event)).hexdigest()
                            if row.get("previousHash") != witness_previous or row.get("hash") != expected_row:
                                return {"ok": False, "records": records, "witnessRecords": witness_records, "error": "witness chain mismatch", "witnessLine": line_number}
                            witness_id = str(event["witnessId"]); record_hash = str(event["recordHash"])
                            secret = policy["witnesses"].get(witness_id)
                            if secret is None or record_hash not in record_hashes:
                                return {"ok": False, "records": records, "witnessRecords": witness_records, "error": "witness identity or record unavailable"}
                            payload = {"version": 1, "witnessId": witness_id, "recordHash": record_hash, "issuedAtNs": int(event["issuedAtNs"])}
                            expected = hmac.new(secret, _canonical({"purpose": "org.upp.public-record-witness/1", "payload": payload}), hashlib.sha256).hexdigest()
                            if not hmac.compare_digest(expected, str(event.get("hmacSha256", ""))):
                                return {"ok": False, "records": records, "witnessRecords": witness_records, "error": "witness authentication mismatch"}
                            witness_counts[record_hash].add(witness_id)
                            witness_previous = expected_row; witness_records += 1
                except (OSError, json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError, ValueError) as exc:
                    return {"ok": False, "records": records, "witnessRecords": witness_records, "error": str(exc)}
            quorum = int(policy["quorum"])
            witnessed = sum(1 for digest in record_hashes if len(witness_counts.get(digest, set())) >= quorum) if quorum else 0
            return {
                "ok": True,
                "records": records,
                "head": previous,
                "signerId": self.signer_id,
                "signatureAlgorithm": "hmac-sha256",
                "externalWitnessConfigured": bool(policy["witnesses"]),
                "witnessQuorum": quorum,
                "witnessRecords": witness_records,
                "quorumWitnessedRecords": witnessed,
                "allRecordsWitnessed": bool(records) and bool(quorum) and witnessed == records,
            }
