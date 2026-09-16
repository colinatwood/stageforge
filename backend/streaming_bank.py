from __future__ import annotations
import hashlib
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any
from daw_media import resolve_media_path

MAX_BANKS=16;MAX_ENTRIES=64

class StreamingSampleBanks:
 def __init__(self,media_root:Path,producer:Any)->None:self.root=Path(media_root);self.producer=producer;self.lock=RLock();self.banks={};self.generation=0;self.triggers=0;self.failures=0;self.action_ids:OrderedDict[str,dict[str,Any]]=OrderedDict()
 def _digest(self,path:Path)->str:
  hasher=hashlib.sha256()
  with path.open("rb") as stream:
   for block in iter(lambda:stream.read(1024*1024),b""):hasher.update(block)
  return "sha256:"+hasher.hexdigest()
 def _clips(self,session:dict[str,Any])->dict[str,dict[str,Any]]:return {str(c.get("clipId")):c for t in session.get("tracks",[]) for c in t.get("clips",[])}
 def replace(self,session:dict[str,Any],bank_id:str,entries:list[dict[str,Any]])->dict[str,Any]:
  bank_id=str(bank_id).strip()[:128]
  if not bank_id:raise ValueError("bankId is required")
  if not entries or len(entries)>MAX_ENTRIES:raise ValueError("bank requires 1..64 entries")
  clips=self._clips(session);built=[];seen=set()
  for index,item in enumerate(entries):
   clip_id=str(item.get("clipId","")).strip();clip=clips.get(clip_id)
   if not clip or clip_id in seen:raise ValueError("bank entry must reference a unique DAW clip")
   source=clip.get("source") or {}
   if source.get("type")!="audio-file":raise ValueError("streaming banks require audio-file clips")
   uri=str(source.get("uri",""));path=resolve_media_path(self.root,uri[6:] if uri.startswith("media/") else uri);digest=self._digest(path);declared=str(source.get("contentHash",""))
   if declared and declared!=digest:raise ValueError("streaming bank content hash mismatch")
   seen.add(clip_id);built.append({"slot":index,"clipId":clip_id,"label":str(item.get("label",clip_id))[:128],"contentHash":digest,"frames":int(clip.get("lengthFrames",0)),"mode":"loop" if item.get("loop") else "oneshot"})
  with self.lock:
   if bank_id not in self.banks and len(self.banks)>=MAX_BANKS:raise RuntimeError("streaming bank capacity reached")
   self.generation+=1;self.banks[bank_id]={"bankId":bank_id,"generation":self.generation,"entries":built}
  return self.status()
 def trigger(self,session:dict[str,Any],bank_id:str,slot:int,action_id:str="")->dict[str,Any]:
  action_id=str(action_id).strip()[:128]
  with self.lock:
   if action_id and action_id in self.action_ids:return {**deepcopy(self.action_ids[action_id]),"deduplicated":True}
  with self.lock:bank=deepcopy(self.banks.get(str(bank_id)))
  if not bank or slot<0 or slot>=len(bank["entries"]):raise ValueError("streaming bank slot unavailable")
  entry=bank["entries"][slot];clip=self._clips(session).get(entry["clipId"]);source=(clip or {}).get("source") or {};uri=str(source.get("uri",""));path=resolve_media_path(self.root,uri[6:] if uri.startswith("media/") else uri)
  if self._digest(path)!=entry["contentHash"]:raise ValueError("streaming bank media changed; replace or relink the bank")
  try:result=self.producer.start_clip(session,entry["clipId"],loop=entry["mode"]=="loop")
  except Exception:
   with self.lock:self.failures+=1
   raise
  response={**result,"bankId":bank["bankId"],"bankGeneration":bank["generation"],"slot":slot,"physicalOutputsArmed":False}
  with self.lock:
   self.triggers+=1
   if action_id:self.action_ids[action_id]=deepcopy(response)
   while len(self.action_ids)>256:self.action_ids.popitem(last=False)
  return response
 def status(self)->dict[str,Any]:
  with self.lock:return {"documentType":"org.upp.streaming-sample-banks","schemaVersion":2,"capacity":MAX_BANKS,"maximumEntriesPerBank":MAX_ENTRIES,"generation":self.generation,"banks":deepcopy(list(self.banks.values())),"triggers":self.triggers,"failures":self.failures,"voiceFeeders":self.producer.status() if hasattr(self.producer,"status") else None,"blockFrames":256,"diskIoInAudioCallback":False,"physicalOutputsArmed":False}
