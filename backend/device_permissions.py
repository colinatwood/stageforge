from __future__ import annotations

import os
import pwd
import stat
from pathlib import Path
from typing import Iterable

_VALID_MODES = frozenset({"r", "w", "rw"})


def parse_device_spec(value: str) -> tuple[Path, str]:
    text = str(value or "").strip()
    if not text:
        raise ValueError("device permission spec must not be empty")
    if ":" in text:
        raw_path, mode = text.rsplit(":", 1)
    else:
        raw_path, mode = text, "rw"
    path = Path(raw_path)
    mode = mode.lower().strip()
    if not path.is_absolute():
        raise ValueError("device permission path must be absolute")
    if mode not in _VALID_MODES:
        raise ValueError("device permission mode must be r, w or rw")
    return path, mode


def _effective_access(path: Path, mode: str) -> bool:
    mask = 0
    if "r" in mode:
        mask |= os.R_OK
    if "w" in mode:
        mask |= os.W_OK
    try:
        return bool(os.access(path, mask, effective_ids=True))
    except TypeError:
        return bool(os.access(path, mask))


def inspect_device(path: Path, mode: str) -> dict:
    try:
        info = path.lstat()
    except OSError as exc:
        return {"path": str(path), "mode": mode, "present": False, "allowed": False,
                "reason": f"device is unavailable: {exc.__class__.__name__}"}
    if stat.S_ISLNK(info.st_mode):
        return {"path": str(path), "mode": mode, "present": True, "characterDevice": False,
                "allowed": False, "reason": "symlink device paths are not accepted"}
    if not stat.S_ISCHR(info.st_mode):
        return {"path": str(path), "mode": mode, "present": True, "characterDevice": False,
                "allowed": False, "reason": "path is not a character device"}
    return {"path": str(path), "mode": mode, "present": True, "characterDevice": True,
            "major": os.major(info.st_rdev), "minor": os.minor(info.st_rdev),
            "uid": int(info.st_uid), "gid": int(info.st_gid),
            "permissions": f"{stat.S_IMODE(info.st_mode):04o}",
            "allowed": _effective_access(path, mode),
            "reason": None}


def qualify_device_permissions(*, service_user: str, device_specs: Iterable[str]) -> dict:
    username = str(service_user or "").strip()
    if not username:
        raise ValueError("service user is required")
    try:
        target = pwd.getpwnam(username)
    except KeyError as exc:
        raise ValueError("service user does not exist") from exc
    current_uid = os.geteuid()
    current_user = pwd.getpwuid(current_uid).pw_name
    identity_ok = current_uid == target.pw_uid
    specs = [parse_device_spec(value) for value in device_specs]
    if not specs:
        raise ValueError("at least one explicit device permission spec is required")
    devices = [inspect_device(path, mode) for path, mode in specs] if identity_ok else []
    all_allowed = identity_ok and all(item.get("allowed") is True for item in devices)
    return {
        "qualification": "service-device-permissions",
        "serviceUser": username,
        "currentUser": current_user,
        "serviceUid": int(target.pw_uid),
        "effectiveUid": int(current_uid),
        "serviceIdentityQualified": identity_ok,
        "devices": devices,
        "hardwarePermissionsQualified": bool(all_allowed),
        "passed": bool(all_allowed),
        "physicalOutputsArmed": False,
    }
