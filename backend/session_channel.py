from __future__ import annotations

import hashlib
import hmac
import json
import struct
from typing import Any, Iterable


MAGIC=b"UPPF";VERSION=1;MAX_PAYLOAD=4096
_PREFIX=struct.Struct(">4sBBH16sQQQI")
HEADER_SIZE=_PREFIX.size+32


def _canonical(value: object) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")


def _session_bytes(session_id: str) -> bytes:
    try:value=bytes.fromhex(session_id)
    except ValueError as exc:raise ValueError("session id must be 32 hexadecimal characters") from exc
    if len(value)!=16:raise ValueError("session id must be 32 hexadecimal characters")
    return value


def derive_direction_key(root_key: bytes,transcript_sha256: str,key_epoch: int,direction: str) -> bytes:
    if not root_key or len(transcript_sha256)!=64 or key_epoch<1 or not direction:raise ValueError("invalid channel key inputs")
    context=b"UPP-SESSION-CHANNEL-V1\0"+bytes.fromhex(transcript_sha256)+int(key_epoch).to_bytes(8,"big")+direction.encode("utf-8")
    return hmac.new(root_key,context,hashlib.sha256).digest()


class AuthenticatedSessionChannel:
    """Bounded integrity/authentication framing; confidentiality is transport-owned."""
    def __init__(self,root_key:bytes,session_id:str,transcript_sha256:str,allowed_capabilities:Iterable[int],*,send_direction:str,receive_direction:str,key_epoch:int=1,rotation_grace_frames:int=32)->None:
        self.root_key=bytes(root_key);self.session_id=session_id;self.session_bytes=_session_bytes(session_id);self.transcript_sha256=transcript_sha256
        self.allowed={int(value) for value in allowed_capabilities if int(value)>0};self.send_direction=send_direction;self.receive_direction=receive_direction
        self.key_epoch=int(key_epoch);self.previous_key_epoch=0;self.rotation_grace_frames=max(0,min(int(rotation_grace_frames),1024));self.previous_accept_until=0
        self.outbound_sequence=0;self.inbound_sequence=0;self.accepted=0;self.rejected=0
        derive_direction_key(self.root_key,self.transcript_sha256,self.key_epoch,self.send_direction)

    def encode(self,capability_id:int,payload:bytes)->bytes:
        capability_id=int(capability_id);payload=bytes(payload)
        if capability_id not in self.allowed:raise PermissionError("capability is outside the negotiated session scope")
        if len(payload)>MAX_PAYLOAD:raise ValueError("session payload exceeds 4096 bytes")
        self.outbound_sequence+=1
        prefix=_PREFIX.pack(MAGIC,VERSION,0,HEADER_SIZE,self.session_bytes,self.key_epoch,self.outbound_sequence,capability_id,len(payload))
        key=derive_direction_key(self.root_key,self.transcript_sha256,self.key_epoch,self.send_direction);tag=hmac.new(key,prefix+payload,hashlib.sha256).digest()
        return prefix+tag+payload

    def decode(self,frame:bytes)->dict[str,Any]:
        try:
            if len(frame)<HEADER_SIZE:raise ValueError("truncated session frame")
            magic,version,flags,header_size,session,key_epoch,sequence,capability,size=_PREFIX.unpack(frame[:_PREFIX.size])
            if magic!=MAGIC or version!=VERSION or flags!=0 or header_size!=HEADER_SIZE:raise ValueError("unsupported session frame header")
            if session!=self.session_bytes:raise ValueError("session frame identity mismatch")
            if size>MAX_PAYLOAD or len(frame)!=HEADER_SIZE+size:raise ValueError("session frame size mismatch")
            if capability not in self.allowed:raise PermissionError("capability is outside the negotiated session scope")
            if sequence<=self.inbound_sequence:raise ValueError("replayed or reordered session frame")
            current=key_epoch==self.key_epoch;previous=key_epoch==self.previous_key_epoch and sequence<=self.previous_accept_until
            if not current and not previous:raise ValueError("session key epoch is not accepted")
            payload=frame[HEADER_SIZE:];supplied=frame[_PREFIX.size:HEADER_SIZE]
            key=derive_direction_key(self.root_key,self.transcript_sha256,key_epoch,self.receive_direction)
            if not hmac.compare_digest(supplied,hmac.new(key,frame[:_PREFIX.size]+payload,hashlib.sha256).digest()):raise ValueError("session frame authentication failed")
        except (ValueError,PermissionError,struct.error):
            self.rejected+=1;raise
        self.inbound_sequence=sequence;self.accepted+=1
        return {"sessionId":self.session_id,"keyEpoch":key_epoch,"sequence":sequence,"capabilityId":capability,"payload":payload,"authenticated":True,"confidential":False,"physicalOutputsArmed":False}

    def rotate(self,new_epoch:int)->None:
        new_epoch=int(new_epoch)
        if new_epoch<=self.key_epoch:raise ValueError("session key epoch must advance")
        self.previous_key_epoch=self.key_epoch;self.key_epoch=new_epoch;self.previous_accept_until=self.inbound_sequence+self.rotation_grace_frames

    def checkpoint(self)->dict[str,Any]:
        payload={"documentType":"org.upp.session-channel-checkpoint","schemaVersion":1,"sessionId":self.session_id,"transcriptSha256":self.transcript_sha256,
                 "keyEpoch":self.key_epoch,"previousKeyEpoch":self.previous_key_epoch,"previousAcceptUntil":self.previous_accept_until,
                 "outboundSequence":self.outbound_sequence,"inboundSequence":self.inbound_sequence,"allowedCapabilities":sorted(self.allowed)}
        return {**payload,"hmacSha256":hmac.new(self.root_key,_canonical(payload),hashlib.sha256).hexdigest()}

    def restore(self,checkpoint:dict[str,Any])->None:
        payload={key:value for key,value in checkpoint.items() if key!="hmacSha256"};expected=hmac.new(self.root_key,_canonical(payload),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,str(checkpoint.get("hmacSha256",""))):raise ValueError("channel checkpoint authentication failed")
        if payload.get("sessionId")!=self.session_id or payload.get("transcriptSha256")!=self.transcript_sha256:raise ValueError("channel checkpoint identity mismatch")
        if {int(value) for value in payload.get("allowedCapabilities",[])}!=self.allowed:raise ValueError("channel checkpoint capability scope mismatch")
        self.key_epoch=int(payload["keyEpoch"]);self.previous_key_epoch=int(payload["previousKeyEpoch"]);self.previous_accept_until=int(payload["previousAcceptUntil"])
        self.outbound_sequence=int(payload["outboundSequence"]);self.inbound_sequence=int(payload["inboundSequence"])

    def status(self)->dict[str,Any]:
        return {"sessionId":self.session_id,"keyEpoch":self.key_epoch,"previousKeyEpoch":self.previous_key_epoch,"outboundSequence":self.outbound_sequence,
                "inboundSequence":self.inbound_sequence,"accepted":self.accepted,"rejected":self.rejected,"capabilityCount":len(self.allowed),
                "authenticated":True,"confidential":False,"physicalOutputsArmed":False}
