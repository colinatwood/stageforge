from __future__ import annotations

from copy import deepcopy
import json,math,os,tempfile
from pathlib import Path
from threading import RLock
from typing import Any

TARGETS=[
 {"targetId":"sample.trigger","name":"Trigger selected sample","kind":"trigger","suggestedControl":"pad","quantize":"1/16","keySync":True},
 {"targetId":"loop.toggle","name":"Start / stop selected loop","kind":"toggle","suggestedControl":"pad","quantize":"1/4","keySync":True},
 {"targetId":"loop.clear","name":"Clear selected loop","kind":"trigger","suggestedControl":"pad","quantize":"1/4","keySync":False},
 {"targetId":"filter.cutoff","name":"Filter cutoff","kind":"continuous","suggestedControl":"knob","minimum":20.0,"maximum":20000.0,"curve":"log","parameterId":1},
 {"targetId":"filter.resonance","name":"Filter resonance","kind":"continuous","suggestedControl":"knob","minimum":0.0,"maximum":1.0,"parameterId":2},
 {"targetId":"oscillator.pitch","name":"Oscillator pitch","kind":"continuous","suggestedControl":"knob","minimum":-24.0,"maximum":24.0,"parameterId":3,"keySync":True},
 {"targetId":"track.volume","name":"Selected track volume","kind":"continuous","suggestedControl":"slider","minimum":0.0,"maximum":1.0,"parameterId":4},
 {"targetId":"track.pan","name":"Selected track pan","kind":"continuous","suggestedControl":"knob","minimum":-1.0,"maximum":1.0,"parameterId":5},
 {"targetId":"transport.play","name":"Play","kind":"trigger","suggestedControl":"pad","quantize":"1/4"},
 {"targetId":"transport.stop","name":"Stop","kind":"trigger","suggestedControl":"pad","quantize":"1/4"},
 {"targetId":"master.tempo","name":"Master tempo","kind":"continuous","suggestedControl":"slider","minimum":30.0,"maximum":300.0,"parameterId":6},
 {"targetId":"instrument.note","name":"Key-synced instrument note","kind":"note","suggestedControl":"pad","quantize":"1/16","keySync":True},
]
TARGET_BY_ID={item["targetId"]:item for item in TARGETS}
KEY_PITCH={"C":0,"Db":1,"D":2,"Eb":3,"E":4,"F":5,"Gb":6,"G":7,"Ab":8,"A":9,"Bb":10,"B":11}
SCALE_INTERVALS={"major":(0,2,4,5,7,9,11),"minor":(0,2,3,5,7,8,10),"chromatic":tuple(range(12))}

def _atomic_json(path:Path,value:dict[str,Any])->None:
 path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(prefix=".midi-map-",suffix=".json",dir=path.parent)
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as stream:json.dump(value,stream,indent=2,sort_keys=True);stream.write("\n");stream.flush();os.fsync(stream.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def _message(event:dict[str,Any])->tuple[str,int,int,int]:
 status=int(event.get("status",0));data1=int(event.get("data1",0));data2=int(event.get("data2",0));high=status&0xF0
 if not 0<=status<=255 or not 0<=data1<=127 or not 0<=data2<=127:raise ValueError("MIDI bytes out of range")
 if high==0x90 and data2>0:return "note",data1,data2,status&15
 if high==0x80 or (high==0x90 and data2==0):return "note-off",data1,data2,status&15
 if high==0xB0:return "cc",data1,data2,status&15
 if high==0xE0:return "pitch-bend",0,data1|(data2<<7),status&15
 if high==0xC0:return "program",data1,data1,status&15
 return "other",data1,data2,status&15

def _quantized_time(seconds:float,bpm:float,division:str)->float:
 fractions={"off":0.0,"1/4":1.0,"1/8":.5,"1/16":.25,"1/32":.125};beats=fractions.get(division,.25)
 if beats<=0:return max(0.0,seconds)
 step=60.0/max(30.0,min(300.0,bpm))*beats
 return math.ceil(max(0.0,seconds)/step-1e-12)*step

def _key_note(note:int,key:str,scale:str)->int:
 root=KEY_PITCH.get(key,0);allowed=SCALE_INTERVALS.get(scale,SCALE_INTERVALS["major"]);candidates=[]
 for candidate in range(max(0,note-6),min(127,note+6)+1):
  if (candidate-root)%12 in allowed:candidates.append(candidate)
 return min(candidates,key=lambda value:(abs(value-note),value)) if candidates else note

class MidiMappingEngine:
 def __init__(self,path:Path)->None:
  self.path=Path(path);self.lock=RLock();self.revision=0;self.mappings:list[dict[str,Any]]=[];self.learning:dict[str,Any]|None=None;self.executions:list[dict[str,Any]]=[];self.pending:list[dict[str,Any]]=[];self._toggles:dict[str,bool]={};self._relative:dict[str,float]={};self._load()
 def _load(self)->None:
  if not self.path.exists():return
  value=json.loads(self.path.read_text("utf-8"));self.revision=max(0,int(value.get("revision",0)));self.mappings=[dict(item) for item in value.get("mappings",[]) if isinstance(item,dict)][:512]
 def _save(self)->None:_atomic_json(self.path,{"documentType":"org.upp.midi-mapping-set","schemaVersion":1,"revision":self.revision,"mappings":self.mappings})
 def targets(self)->dict[str,Any]:return {"targets":deepcopy(TARGETS),"masterSync":{"clock":"show-time","beatDivisions":["off","1/4","1/8","1/16","1/32"],"scales":list(SCALE_INTERVALS)},"physicalOutputsArmed":False}
 def status(self)->dict[str,Any]:
  with self.lock:return {"documentType":"org.upp.midi-mapping-status","schemaVersion":1,"revision":self.revision,"learning":deepcopy(self.learning),"mappings":deepcopy(self.mappings),"pendingActions":deepcopy(self.pending[:64]),"recentExecutions":deepcopy(self.executions[-32:]),"physicalOutputsArmed":False}
 def begin(self,request:dict[str,Any])->dict[str,Any]:
  target_id=str(request.get("targetId","")).strip();preset=TARGET_BY_ID.get(target_id)
  if not preset:raise ValueError("choose a supported mapping target")
  with self.lock:
   target=deepcopy(preset);resource_id=str(request.get("resourceId","")).strip()[:128]
   if resource_id:target["resourceId"]=resource_id
   self.learning={"target":target,"deviceId":str(request.get("deviceId",""))[:96],"behavior":str(request.get("behavior","auto")),"quantize":str(request.get("quantize",preset.get("quantize","off"))),"keySync":bool(request.get("keySync",preset.get("keySync",False))),"scale":str(request.get("scale","major")),"state":"waiting-for-gesture"}
   return self.status()
 def cancel(self)->dict[str,Any]:
  with self.lock:self.learning=None;return self.status()
 def delete(self,mapping_id:str)->dict[str,Any]:
  with self.lock:
   kept=[item for item in self.mappings if item.get("mappingId")!=mapping_id]
   if len(kept)==len(self.mappings):raise KeyError(mapping_id)
   self.mappings=kept;self.revision+=1;self._save();return self.status()
 def observe(self,event:dict[str,Any],transport:dict[str,Any])->dict[str,Any]:
  message,number,raw_value,channel=_message(event);learned=None
  with self.lock:
   learn=self.learning
   device_id=str(event.get("deviceId","direct"))[:96]
   if learn and message not in {"other","note-off"} and (not learn["deviceId"] or learn["deviceId"]==device_id):
    target=learn["target"];behavior=learn["behavior"]
    if behavior=="auto":behavior="relative" if message=="cc" and target["kind"]=="continuous" and raw_value in {1,127} else "absolute" if message in {"cc","pitch-bend"} and target["kind"]=="continuous" else "gate" if target["kind"]=="note" else target["kind"]
    self.revision+=1;identity=(device_id,channel,message,number)
    self.mappings=[item for item in self.mappings if (item["source"]["deviceId"],item["source"]["channel"],item["source"]["message"],item["source"]["number"])!=identity]
    learned={"mappingId":f"map-{self.revision}","name":target["name"],"source":{"deviceId":device_id,"channel":channel,"message":message,"number":number},"target":deepcopy(target),"behavior":behavior,"quantize":learn["quantize"],"keySync":learn["keySync"],"scale":learn["scale"],"enabled":True}
    self.mappings.append(learned);self.learning=None;self._save()
   actions=[]
   for mapping in self.mappings:
    source=mapping["source"]
    if not mapping.get("enabled",True) or source["deviceId"]!=device_id or source["channel"]!=channel or source["message"]!=message or source["number"]!=number:continue
    target=mapping["target"];behavior=mapping["behavior"]
    if message=="note" and raw_value==0:continue
    if message=="pitch-bend":normalized=raw_value/16383.0
    else:normalized=raw_value/127.0
    if behavior=="relative":
     delta=raw_value if raw_value<=63 else raw_value-128;normalized=max(0.0,min(1.0,self._relative.get(mapping["mappingId"],.5)+delta/127.0));self._relative[mapping["mappingId"]]=normalized
    minimum=float(target.get("minimum",0.0));maximum=float(target.get("maximum",1.0));curve=target.get("curve","linear")
    scaled=minimum*(maximum/minimum)**normalized if curve=="log" and minimum>0 else minimum+(maximum-minimum)*normalized
    if behavior=="toggle":self._toggles[mapping["mappingId"]]=not self._toggles.get(mapping["mappingId"],False);value=1.0 if self._toggles[mapping["mappingId"]] else 0.0
    elif behavior in {"trigger","gate"}:value=1.0
    else:value=scaled
    seconds=float(event.get("showTimeSeconds",transport.get("seconds",0.0)));bpm=float(transport.get("bpm",120));division=mapping.get("quantize","off") if transport.get("running",True) else "off";show_time=_quantized_time(seconds,bpm,division)
    action={"mappingId":mapping["mappingId"],"targetId":target["targetId"],"value":round(value,9),"showTimeSeconds":round(show_time,9),"quantized":show_time>seconds+1e-9,"masterBpm":bpm,"masterKey":str(transport.get("key","C")),"source":deepcopy(source)}
    if mapping.get("keySync") and message=="note":
     output=_key_note(number,action["masterKey"],mapping.get("scale","major"));action.update({"inputNote":number,"outputNote":output,"transposeSemitones":output-number,"scale":mapping.get("scale","major")})
    if "parameterId" in target:action["parameterId"]=int(target["parameterId"])
    if target.get("resourceId"):action["resourceId"]=target["resourceId"]
    actions.append(action);self.pending.append(action)
   self.pending=self.pending[-1024:]
   return {"learnedMapping":deepcopy(learned),"actions":deepcopy(actions),"physicalOutputsArmed":False}
 def drain_due(self,show_time_seconds:float)->list[dict[str,Any]]:
  with self.lock:
   due=[item for item in self.pending if float(item["showTimeSeconds"])<=show_time_seconds+1e-9];self.pending=[item for item in self.pending if float(item["showTimeSeconds"])>show_time_seconds+1e-9];self.executions.extend(due);self.executions=self.executions[-256:];return deepcopy(due)
