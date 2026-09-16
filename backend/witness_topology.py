"""Strict independent-witness deployment topology.

A list of URLs is not evidence of independence.  This file-backed topology pins
one identity, one declared failure domain and one independently rotated HMAC
keyring per witness.  It is control-plane configuration and is never consulted
from a real-time callback.
"""
from __future__ import annotations

import ipaddress
import json
import os
import stat
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from cluster_secrets import RotatingHmacKeyring

_MAX_BYTES = 65536
_MAX_WITNESSES = 9


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_private(path: Path) -> bytes:
    try:
        if not path.is_absolute():
            raise ValueError("absolute topology path required")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or stat.S_IMODE(before.st_mode) & 0o077 or before.st_size > _MAX_BYTES):
                raise ValueError("invalid topology file")
            data = stream.read(_MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            if (len(data) > _MAX_BYTES
                    or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                raise ValueError("topology file changed while reading")
        return data
    except (OSError, ValueError):
        raise PermissionError("independent witness topology unavailable or invalid") from None


def _identifier(value: Any, field: str) -> str:
    text = str(value).strip()
    if (not 1 <= len(text) <= 64 or not text.isascii()
            or any(not (ch.isalnum() or ch in "._-") for ch in text)):
        raise ValueError(f"invalid {field}")
    return text


def _loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_witness_topology(path: str | os.PathLike[str]) -> dict[str, Any]:
    try:
        document = json.loads(_read_private(Path(path)).decode("utf-8"), object_pairs_hook=_unique_pairs)
        if (not isinstance(document, dict)
                or set(document) != {"version", "quorum", "maxClockSkewMs", "allowInsecureLoopback", "witnesses"}
                or document.get("version") != 1):
            raise ValueError("invalid topology root")
        witnesses = document.get("witnesses")
        quorum = document.get("quorum")
        skew = document.get("maxClockSkewMs")
        allow_insecure = document.get("allowInsecureLoopback")
        if (not isinstance(witnesses, list) or not 1 <= len(witnesses) <= _MAX_WITNESSES
                or type(quorum) is not int or type(skew) is not int or type(allow_insecure) is not bool):
            raise ValueError("invalid topology fields")
        majority = len(witnesses) // 2 + 1
        if not majority <= quorum <= len(witnesses):
            raise ValueError("independent witness quorum must be a majority")
        if not 50 <= skew <= 10000:
            raise ValueError("maxClockSkewMs must be 50..10000")

        urls: set[str] = set(); ids: set[str] = set(); domains: set[str] = set(); keyring_paths: set[str] = set()
        normalized = []
        for raw in witnesses:
            if not isinstance(raw, dict) or set(raw) != {"url", "witnessId", "failureDomain", "keyringFile"}:
                raise ValueError("invalid witness topology entry")
            url = str(raw["url"]).strip().rstrip("/")
            parsed = urlparse(url)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
                raise ValueError("invalid witness URL")
            if parsed.scheme != "https" and not (allow_insecure and _loopback_host(parsed.hostname)):
                raise ValueError("independent witnesses require HTTPS outside loopback qualification")
            witness_id = _identifier(raw["witnessId"], "witnessId")
            failure_domain = _identifier(raw["failureDomain"], "failureDomain")
            keyring_file = str(raw["keyringFile"]).strip()
            if not os.path.isabs(keyring_file):
                raise ValueError("witness keyringFile must be absolute")
            if url in urls or witness_id in ids or failure_domain in domains or keyring_file in keyring_paths:
                raise ValueError("independent witness URLs, identities, failure domains and keyrings must be unique")
            # Fail startup closed and prove each endpoint keyring is private/readable.
            RotatingHmacKeyring(keyring_file).snapshot()
            urls.add(url); ids.add(witness_id); domains.add(failure_domain); keyring_paths.add(keyring_file)
            normalized.append({
                "url": url,
                "witnessId": witness_id,
                "failureDomain": failure_domain,
                "keyringFile": keyring_file,
            })
        return {
            "version": 1,
            "quorum": quorum,
            "maxClockSkewMs": skew,
            "allowInsecureLoopback": allow_insecure,
            "witnesses": normalized,
        }
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, AttributeError, RecursionError):
        raise PermissionError("independent witness topology unavailable or invalid") from None
