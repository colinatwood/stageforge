from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


_PURPOSE = "org.upp.community-account-session/1"
_MAX_TOKEN_BYTES = 2048
_MIN_TTL_SECONDS = 60
_MAX_TTL_SECONDS = 86400


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    if not value or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in value):
        raise PermissionError("invalid community session credential")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception:
        raise PermissionError("invalid community session credential") from None


def _valid_account_id(value: str) -> bool:
    return bool(value and len(value) <= 128 and value == value.strip()
                and all(ord(char) >= 32 and ord(char) != 127 for char in value))


@dataclass(frozen=True)
class CommunitySession:
    account_id: str
    auth_generation: int
    session_id: str
    issued_at_ns: int
    expires_at_ns: int


class CommunitySessionManager:
    """Short-lived signed account sessions for community governance.

    Tokens are stateless bearer credentials. Revocation is account-scoped through
    the persisted auth generation supplied by CommunityGovernance. The signing
    key is domain-separated from other uses by the signed purpose field.
    """

    def __init__(self, signing_secret: bytes, *, ttl_seconds: int = 900) -> None:
        if not isinstance(signing_secret, (bytes, bytearray)) or len(signing_secret) < 32:
            raise ValueError("community session signing secret is too short")
        self._secret = bytes(signing_secret)
        self.ttl_seconds = max(_MIN_TTL_SECONDS, min(_MAX_TTL_SECONDS, int(ttl_seconds)))

    def issue(self, account_id: str, auth_generation: int, *, now_ns: int | None = None) -> dict[str, Any]:
        account_id = str(account_id).strip()
        if not _valid_account_id(account_id):
            raise ValueError("invalid community account identity")
        generation = int(auth_generation)
        if generation < 1:
            raise ValueError("invalid community account auth generation")
        issued = time.time_ns() if now_ns is None else int(now_ns)
        expires = issued + self.ttl_seconds * 1_000_000_000
        payload = {
            "version": 1,
            "purpose": _PURPOSE,
            "accountId": account_id,
            "authGeneration": generation,
            "sessionId": "community-session-" + secrets.token_hex(16),
            "issuedAtNs": issued,
            "expiresAtNs": expires,
        }
        encoded = _b64url_encode(_canonical(payload))
        signature = hmac.new(self._secret, _PURPOSE.encode("ascii") + b"\n" + encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return {
            "sessionToken": encoded + "." + signature,
            "accountId": account_id,
            "authGeneration": generation,
            "sessionId": payload["sessionId"],
            "issuedAtNs": issued,
            "expiresAtNs": expires,
            "expiresInSeconds": self.ttl_seconds,
        }

    def verify(self, token: str, *, now_ns: int | None = None) -> CommunitySession:
        raw = str(token).strip()
        if not raw or len(raw.encode("utf-8")) > _MAX_TOKEN_BYTES or raw.count(".") != 1:
            raise PermissionError("invalid community session credential")
        encoded, supplied = raw.split(".", 1)
        if len(supplied) != 64 or any(ch not in "0123456789abcdef" for ch in supplied):
            raise PermissionError("invalid community session credential")
        expected = hmac.new(self._secret, _PURPOSE.encode("ascii") + b"\n" + encoded.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            raise PermissionError("community session authentication failed")
        try:
            payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PermissionError("invalid community session credential") from None
        if not isinstance(payload, dict) or set(payload) != {
            "version", "purpose", "accountId", "authGeneration", "sessionId", "issuedAtNs", "expiresAtNs"
        }:
            raise PermissionError("invalid community session credential")
        try:
            account_id = str(payload["accountId"])
            generation = int(payload["authGeneration"])
            issued = int(payload["issuedAtNs"])
            expires = int(payload["expiresAtNs"])
            session_id = str(payload["sessionId"])
        except (KeyError, TypeError, ValueError):
            raise PermissionError("invalid community session credential") from None
        if (payload.get("version") != 1 or payload.get("purpose") != _PURPOSE or not _valid_account_id(account_id)
                or generation < 1 or not session_id.startswith("community-session-") or len(session_id) != 50
                or issued <= 0 or expires <= issued or expires - issued > _MAX_TTL_SECONDS * 1_000_000_000):
            raise PermissionError("invalid community session credential")
        now = time.time_ns() if now_ns is None else int(now_ns)
        if now < issued - 5_000_000_000:
            raise PermissionError("community session is not yet valid")
        if now > expires:
            raise PermissionError("community session has expired")
        return CommunitySession(account_id, generation, session_id, issued, expires)
