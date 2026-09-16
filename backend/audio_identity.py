"""Privacy-preserving cross-platform audio endpoint identity for conservative reconnect."""
from __future__ import annotations
import hashlib,json,os,re
from pathlib import Path
from threading import RLock


def _read(path:Path)->str:
    try:return path.read_text(errors="replace").strip()[:256]
    except OSError:return ""


def _hashed_token(value:object)->str|None:
    text=str(value or "").strip().lower()
    return text if re.fullmatch(r"sha256:[0-9a-f]{64}",text) else None


def _engine_identity_metadata(value:object)->dict[str,str]:
    text=str(value or "").strip()
    result={}
    for item in text.split(";"):
        if "=" not in item:continue
        key,val=item.split("=",1)
        if key in {"native","persistent","strength","auto"}:result[key]=val.strip().lower()
    # The engine boundary accepts only hash tokens for identity-bearing fields.
    if result.get("native") and not _hashed_token(result["native"]):result.pop("native",None)
    if result.get("persistent") and not _hashed_token(result["persistent"]):result.pop("persistent",None)
    return result


def describe_audio_device(device:dict,*,sys_root=Path("/sys"),proc_root=Path("/proc"))->dict:
    if device.get("id")=="null-audio":return {"persistentId":"audio-null","identityStrength":"builtin","automaticReconnectEligible":True,"identityScope":"built-in null endpoint"}
    result={"persistentId":None,"identityStrength":"volatile","automaticReconnectEligible":False,"identityScope":"current native endpoint only"}
    backend=str(device.get("backend") or "").lower()
    direction=f"{int(bool(device.get('input')))}{int(bool(device.get('output')))}"
    metadata=_engine_identity_metadata(device.get("address"))
    if backend=="wasapi":
        stable=_hashed_token(device.get("stableIdHash"))
        snapshot=_hashed_token(device.get("instanceIdHash"))
        if not stable and metadata.get("strength")=="os-stable-endpoint" and metadata.get("auto")=="1":stable=_hashed_token(metadata.get("persistent"))
        if not snapshot and metadata.get("strength")=="installation-snapshot":snapshot=_hashed_token(metadata.get("persistent"))
        if stable:
            material=f"wasapi-stable:{stable}:{direction}"
            return {"persistentId":"audio-"+hashlib.sha256(material.encode()).hexdigest()[:24],"identityStrength":"os-stable-endpoint","automaticReconnectEligible":True,"identityScope":"Windows stable endpoint identity hash; mutable endpoint properties must be re-queried"}
        if snapshot:
            material=f"wasapi-installation:{snapshot}:{direction}"
            return {"persistentId":"audio-"+hashlib.sha256(material.encode()).hexdigest()[:24],"identityStrength":"installation-snapshot","automaticReconnectEligible":False,"identityScope":"Windows installation-scoped endpoint hash; explicit recovery required because driver/OS updates can replace it"}
        return {**result,"identityScope":"WASAPI endpoint lacks a persistence-grade identity hash"}
    if backend=="coreaudio":
        uid=_hashed_token(device.get("uidHash"))
        if not uid and metadata.get("strength")=="os-stable-endpoint" and metadata.get("auto")=="1":uid=_hashed_token(metadata.get("persistent"))
        if uid:
            material=f"coreaudio:{uid}:{direction}"
            return {"persistentId":"audio-"+hashlib.sha256(material.encode()).hexdigest()[:24],"identityStrength":"os-stable-endpoint","automaticReconnectEligible":True,"identityScope":"hash of CoreAudio device UID; mutable device properties must be re-queried"}
        return {**result,"identityScope":"CoreAudio endpoint lacks a hashed device UID"}
    if backend!="alsa":return result
    address=str(device.get("address","")).strip()
    match=re.fullmatch(r"(?:plug)?hw:(?:CARD=)?([A-Za-z0-9_-]+)(?:,(?:DEV=)?([0-9]+))?",address,re.I)
    if not match:return {**result,"identityScope":"ALSA alias; hardware identity unavailable"}
    card_token=match.group(1);device_number=match.group(2) or "0";card_number=card_token if card_token.isdigit() else None
    if card_number is None:
        for candidate in range(256):
            if _read(proc_root/"asound"/f"card{candidate}"/"id")==card_token:card_number=str(candidate);break
    if card_number is None:return {**result,"identityScope":"ALSA card name could not be resolved"}
    node=sys_root/"class"/"sound"/f"card{card_number}"/"device"
    try:resolved=node.resolve(strict=True)
    except OSError:return {**result,"identityScope":"ALSA card topology unavailable"}
    usb=None
    for candidate in (resolved,*resolved.parents):
        if _read(candidate/"idVendor") and _read(candidate/"idProduct"):usb=candidate;break
    card_id=_read(proc_root/"asound"/f"card{card_number}"/"id")
    if usb:
        vendor=_read(usb/"idVendor").lower();product=_read(usb/"idProduct").lower();serial=_read(usb/"serial")
        material=f"usb:{vendor}:{product}:{serial}:pcm:{device_number}:{direction}" if serial else f"usb-port:{vendor}:{product}:{resolved}:pcm:{device_number}:{direction}"
        return {"persistentId":"audio-"+hashlib.sha256(material.encode()).hexdigest()[:24],"identityStrength":"hardware-serial" if serial else "topology","automaticReconnectEligible":bool(serial),"identityScope":"USB VID/PID, hashed serial and PCM endpoint" if serial else "USB topology; explicit recovery required","usbHardwareId":f"USB:{vendor.upper()}:{product.upper()}"}
    material=f"alsa:{card_id}:{resolved}:pcm:{device_number}:{direction}"
    return {"persistentId":"audio-"+hashlib.sha256(material.encode()).hexdigest()[:24],"identityStrength":"topology","automaticReconnectEligible":False,"identityScope":"ALSA card identity and topology; explicit recovery required"}


class AudioIdentityStore:
    def __init__(self,path:Path):self.path,self.lock=Path(path),RLock();self.records=self._load()
    def _load(self):
        try:
            value=json.loads(self.path.read_text());return value.get("records",{}) if isinstance(value,dict) and isinstance(value.get("records"),dict) else {}
        except (OSError,ValueError,TypeError):return {}
    def _write(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_name(self.path.name+f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps({"schemaVersion":1,"records":self.records},sort_keys=True,separators=(",",":")))
        os.replace(temporary,self.path)
    def record(self,native_id:str,identity:dict):
        persistent=identity.get("persistentId")
        if not persistent:return None
        record={key:identity.get(key) for key in ("persistentId","identityStrength","automaticReconnectEligible","usbHardwareId")}
        with self.lock:
            # Observation must never replace the identity previously associated with an ID.
            if str(native_id) in self.records:return dict(self.records[str(native_id)])
            self.records[str(native_id)]=record;self._write()
        return dict(record)
    def replace(self,native_id:str,identity:dict):
        persistent=identity.get("persistentId")
        if not persistent:raise ValueError("replacement audio endpoint has no persistent identity")
        record={key:identity.get(key) for key in ("persistentId","identityStrength","automaticReconnectEligible","usbHardwareId")};record["explicitlyRebound"]=True
        with self.lock:
            previous=self.records.get(str(native_id))
            if not isinstance(previous,dict):raise ValueError("desired audio endpoint has no pinned identity to replace")
            self.records[str(native_id)]=record;self._write()
        return dict(previous),dict(record)
    def expected(self,native_id:str):
        with self.lock:value=self.records.get(str(native_id));return dict(value) if isinstance(value,dict) else None
    def reconnect_match(self,prior_native_id:str,devices:list[dict]):
        expected=self.expected(prior_native_id)
        if not expected or (expected.get("automaticReconnectEligible") is not True and expected.get("explicitlyRebound") is not True):return None
        matches=[device for device in devices if device.get("persistentId")==expected.get("persistentId") and (device.get("automaticReconnectEligible") is True or expected.get("explicitlyRebound") is True)]
        return matches[0] if len(matches)==1 else None

    def resolve(self, native_id: str, devices: list[dict], direction: str):
        candidates=[item for item in devices if item.get("connected") and item.get(direction)]
        expected=self.expected(native_id)
        if expected and (expected.get("automaticReconnectEligible") is True or expected.get("explicitlyRebound") is True):
            # Check uniqueness even when the old numeric endpoint still exists.
            return self.reconnect_match(native_id,candidates)
        direct=next((item for item in candidates if item.get("id")==native_id),None)
        if expected and direct and expected.get("persistentId")!=direct.get("persistentId"):
            return None
        return direct
