"""Privacy-preserving MIDI identity evidence for safe reconnect decisions."""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
from threading import RLock


def _read(path):
    try: return path.read_text(errors="replace").strip()[:256]
    except OSError: return ""


def _hashed_token(value):
    text=str(value or "").strip().lower()
    return text if re.fullmatch(r"sha256:[0-9a-f]{64}",text) else None


def _engine_identity_metadata(value):
    result={}
    for item in str(value or "").strip().split(";"):
        if "=" not in item:continue
        key,val=item.split("=",1)
        if key in {"backend","native","persistent","strength","auto"}:result[key]=val.strip().lower()
    if result.get("native") and not _hashed_token(result["native"]):result.pop("native",None)
    if result.get("persistent") and not _hashed_token(result["persistent"]):result.pop("persistent",None)
    return result


def describe_midi_device(device, *, sys_root=Path("/sys")):
    result = {"persistentId": None, "identityStrength": "volatile",
              "automaticRebindEligible": False, "identityScope": "current native endpoint only"}
    metadata=_engine_identity_metadata(device.get("path"))
    backend=str(device.get("backend") or metadata.get("backend") or "").lower()
    if backend=="coremidi":
        unique=_hashed_token(device.get("uniqueIdHash") or device.get("connectionUniqueIdHash"))
        if not unique and metadata.get("strength")=="os-stable-endpoint" and metadata.get("auto")=="1":unique=_hashed_token(metadata.get("persistent"))
        if not unique:return {**result,"identityScope":"CoreMIDI endpoint lacks a hashed unique ID"}
        return {"persistentId":"midi-"+hashlib.sha256(("coremidi:"+unique).encode()).hexdigest()[:24],
                "identityStrength":"os-stable-endpoint","automaticRebindEligible":True,
                "identityScope":"hash of CoreMIDI unique/connection ID"}
    if backend=="windows-midi":
        persistent=_hashed_token(device.get("persistentIdHash") or metadata.get("persistent"))
        verified=device.get("persistentIdentityVerified") is True or (
            metadata.get("strength")=="os-stable-endpoint" and metadata.get("auto")=="1")
        if persistent and verified:
            return {"persistentId":"midi-"+hashlib.sha256(("windows-midi:"+persistent).encode()).hexdigest()[:24],
                    "identityStrength":"os-stable-endpoint","automaticRebindEligible":True,
                    "identityScope":"platform-verified Windows MIDI persistent identity hash"}
        if persistent and metadata.get("strength")=="installation-snapshot":
            return {"persistentId":"midi-"+hashlib.sha256(("windows-midi-installation:"+persistent).encode()).hexdigest()[:24],
                    "identityStrength":"installation-snapshot","automaticRebindEligible":False,
                    "identityScope":"Windows MIDI installation/interface hash; explicit rebind required"}
        return {**result,"identityScope":"Windows MIDI endpoint identity is not verified persistence-grade; explicit rebind required"}
    path = str(device.get("path", ""))
    match = re.fullmatch(r"/dev/snd/(midiC([0-9]{1,3})D([0-9]{1,3}))", path)
    if not match: return result
    node = sys_root / "class/sound" / match.group(1)
    try: resolved = node.resolve(strict=True)
    except OSError: return {**result, "identityScope": "ALSA card/device numbers; sysfs identity unavailable"}
    usb = None
    for candidate in (resolved, *resolved.parents):
        if _read(candidate / "idVendor") and _read(candidate / "idProduct"):
            usb = candidate; break
    card_id = _read(sys_root / "class/sound" / f"card{match.group(2)}" / "id")
    if usb:
        vendor, product, serial = _read(usb / "idVendor").lower(), _read(usb / "idProduct").lower(), _read(usb / "serial")
        material = f"usb:{vendor}:{product}:{serial}" if serial else f"usb-port:{vendor}:{product}:{resolved}"
        strength = "hardware-serial" if serial else "topology"
        return {"persistentId": "midi-" + hashlib.sha256(material.encode()).hexdigest()[:24],
                "identityStrength": strength, "automaticRebindEligible": bool(serial),
                "identityScope": "USB VID/PID and hashed serial" if serial else "USB topology; explicit rebind required",
                "usbHardwareId": f"USB:{vendor.upper()}:{product.upper()}"}
    material = f"alsa:{card_id}:{match.group(3)}:{resolved}"
    return {"persistentId": "midi-" + hashlib.sha256(material.encode()).hexdigest()[:24],
            "identityStrength": "topology", "automaticRebindEligible": False,
            "identityScope": "ALSA card identity and topology; explicit rebind required"}


class MidiIdentityStore:
    def __init__(self, path):
        self.path, self.lock = Path(path), RLock()
        self.records = self._load()

    def _load(self):
        try:
            value = json.loads(self.path.read_text())
            return value.get("records", {}) if isinstance(value, dict) and isinstance(value.get("records"), dict) else {}
        except (OSError, ValueError, TypeError): return {}

    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps({"schemaVersion":1,"records":self.records}, sort_keys=True, separators=(",", ":")))
        os.replace(temporary, self.path)

    def record(self, native_id, identity):
        persistent = identity.get("persistentId")
        if not persistent: return None
        record = {key: identity.get(key) for key in ("persistentId", "identityStrength", "automaticRebindEligible", "usbHardwareId")}
        with self.lock:
            # Discovery is observation, not authority. Once a logical native ID has
            # been pinned, a later device appearing at that same OS/native token must
            # not silently replace the expected physical identity.
            existing = self.records.get(str(native_id))
            if isinstance(existing, dict):
                return dict(existing)
            self.records[str(native_id)] = record
            self._write()
        return dict(record)

    def expected(self, native_id):
        with self.lock:
            value = self.records.get(str(native_id))
            return dict(value) if isinstance(value, dict) else None

    def permits_rebind(self, native_id, identity):
        expected = self.expected(native_id)
        return bool(expected and expected.get("automaticRebindEligible") is True and
                    expected.get("persistentId") == identity.get("persistentId") and
                    identity.get("automaticRebindEligible") is True)

    def reconnect_match(self, prior_native_id, devices):
        expected = self.expected(prior_native_id)
        if not expected or expected.get("automaticRebindEligible") is not True:
            return None
        matches = [device for device in devices
                   if device.get("connected") is not False
                   and device.get("persistentId") == expected.get("persistentId")
                   and device.get("automaticRebindEligible") is True]
        return matches[0] if len(matches) == 1 else None

    def resolve(self, prior_native_id, devices):
        expected = self.expected(prior_native_id)
        if expected and expected.get("automaticRebindEligible") is True:
            # Always check the whole scan for uniqueness. Reusing the old native ID
            # is not enough if a second endpoint claims the same persistent identity.
            return self.reconnect_match(prior_native_id, devices)
        direct = next((device for device in devices
                       if str(device.get("id", "")) == str(prior_native_id)
                       and device.get("connected") is not False), None)
        if expected and direct and expected.get("persistentId") != direct.get("persistentId"):
            return None
        return direct
