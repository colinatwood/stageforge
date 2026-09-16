from __future__ import annotations

from copy import deepcopy
import json, math, os, tempfile
from pathlib import Path
from threading import RLock
from typing import Any

MAX_TRACKS=128;MAX_CLIPS=4096;CANONICAL_RATE=192000

def normalize_session(value:dict[str,Any])->dict[str,Any]:
    result=deepcopy(value)
    tracks=result.get("tracks",[])
    if not isinstance(tracks,list) or len(tracks)>MAX_TRACKS:raise ValueError("tracks must contain at most 128 entries")
    seen_tracks:set[str]=set();seen_clips:set[str]=set();normalized=[];clip_count=0
    for raw in tracks:
        track_id=str(raw.get("trackId","")).strip()[:128]
        if not track_id or track_id in seen_tracks:raise ValueError("track ids must be unique non-empty tokens")
        seen_tracks.add(track_id);kind=str(raw.get("kind","audio"))
        if kind not in {"audio","midi","aux","master"}:raise ValueError("unsupported track kind")
        clips=[]
        for clip in raw.get("clips",[]):
            clip_count+=1
            if clip_count>MAX_CLIPS:raise ValueError("session exceeds 4096 clips")
            clip_id=str(clip.get("clipId","")).strip()[:128]
            start=max(0,int(clip.get("startFrame",0)));length=int(clip.get("lengthFrames",0));offset=max(0,int(clip.get("sourceOffsetFrames",0)))
            if not clip_id or clip_id in seen_clips or length<1:raise ValueError("clip identity and length must be valid")
            seen_clips.add(clip_id)
            source=dict(clip.get("source") or {})
            if source.get("type") not in {"audio-file","midi-sequence","generator"}:raise ValueError("clip source type is unsupported")
            fades=dict(clip.get("fades") or {});fade_in=max(0,int(fades.get("inFrames",0)));fade_out=max(0,int(fades.get("outFrames",0)))
            span=int(fades.get("spanFrames",length));fade_offset=int(fades.get("offsetFrames",0))
            if span<length or fade_offset<0 or fade_offset+length>span:raise ValueError("invalid fade span")
            if fade_in+fade_out>span:raise ValueError("combined fades exceed clip length")
            if fades.get("curve","equal-power") not in {"linear","equal-power"}:raise ValueError("unsupported clip fade curve")
            clips.append({**clip,"clipId":clip_id,"startFrame":start,"lengthFrames":length,"sourceOffsetFrames":offset,"source":source,"muted":bool(clip.get("muted",False)),"fades":{"inFrames":fade_in,"outFrames":fade_out,"curve":str(fades.get("curve","equal-power")),**({"spanFrames":span,"offsetFrames":fade_offset} if "spanFrames" in fades or "offsetFrames" in fades else {})}})
        raw_automation=raw.get("automation") or []
        if not isinstance(raw_automation,list) or len(raw_automation)>4096:raise ValueError("track automation must contain at most 4096 points")
        automation=[];point_ids=set();positions=set()
        for point_index,point in enumerate(raw_automation):
            if not isinstance(point,dict):raise ValueError("automation points must be objects")
            parameter=str(point.get("parameter",""));frame=point.get("frame");value=point.get("value");point_id=str(point.get("pointId",f"{parameter}-{frame}-{point_index}"))[:128]
            if parameter!="volume":raise ValueError("unsupported automation parameter")
            if type(frame) is not int or frame<0 or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=2:raise ValueError("invalid volume automation point")
            if not point_id or point_id in point_ids or (parameter,frame) in positions:raise ValueError("automation point ids and positions must be unique")
            point_ids.add(point_id);positions.add((parameter,frame));automation.append({**point,"pointId":point_id,"parameter":parameter,"frame":frame,"value":float(value),"interpolation":"linear"})
        automation.sort(key=lambda point:(point["parameter"],point["frame"],point["pointId"]));sends=list(raw.get("sends") or [])[:32]
        normalized.append({**raw,"trackId":track_id,"kind":kind,"name":str(raw.get("name",track_id))[:128],"gain":max(0.0,min(4.0,float(raw.get("gain",1.0)))),"pan":max(-1.0,min(1.0,float(raw.get("pan",0.0)))),"muted":bool(raw.get("muted",False)),"solo":bool(raw.get("solo",False)),"outputBus":str(raw.get("outputBus","master"))[:128],"sends":sends,"automation":automation,"clips":clips})
    tempo=list(result.get("tempoMap") or [{"beat":0,"bpm":120,"numerator":4,"denominator":4}])[:1024]
    raw_markers=result.get("markers") or []
    if not isinstance(raw_markers,list) or len(raw_markers)>1024:raise ValueError("markers must contain at most 1024 entries")
    markers=[];marker_ids=set()
    for raw in raw_markers:
        if not isinstance(raw,dict):raise ValueError("markers must be objects")
        marker_id=str(raw.get("markerId","")).strip()[:128];frame=raw.get("frame");kind=str(raw.get("kind","note"))
        if not marker_id or marker_id in marker_ids:raise ValueError("marker ids must be unique non-empty tokens")
        if type(frame) is not int or frame<0:raise ValueError("marker frame must be a non-negative integer")
        if kind not in {"note","section","cue"}:raise ValueError("unsupported marker kind")
        name=str(raw.get("name",marker_id)).strip()[:128] or marker_id
        marker_ids.add(marker_id);markers.append({**raw,"markerId":marker_id,"frame":frame,"name":name,"kind":kind})
    markers.sort(key=lambda marker:(marker["frame"],marker["markerId"]))
    return {**result,"documentType":"org.upp.daw-session","schemaVersion":1,"minimumReaderSchemaVersion":int(result.get("minimumReaderSchemaVersion",1)),"sessionId":str(result.get("sessionId","default"))[:128],"revision":max(0,int(result.get("revision",0))),"sampleRate":CANONICAL_RATE,"sampleFormat":"float32-planar","tempoMap":tempo,"markers":markers,"tracks":normalized,"unknownFieldsPreserved":True,"physicalOutputsArmed":False}

def render_plan(session:dict[str,Any],start_frame:int,end_frame:int)->dict[str,Any]:
    session=normalize_session(session);start=max(0,int(start_frame));end=int(end_frame)
    if end<=start or end-start>CANONICAL_RATE*60*60:raise ValueError("render range must be positive and no longer than one hour")
    solo=any(t["solo"] for t in session["tracks"]);regions=[]
    for track in session["tracks"]:
        audible=not track["muted"] and (not solo or track["solo"])
        for clip in track["clips"]:
            overlap_start=max(start,clip["startFrame"]);overlap_end=min(end,clip["startFrame"]+clip["lengthFrames"])
            if audible and not clip["muted"] and overlap_end>overlap_start:
                regions.append({"trackId":track["trackId"],"clipId":clip["clipId"],"renderStartFrame":overlap_start,"renderFrames":overlap_end-overlap_start,"sourceStartFrame":clip["sourceOffsetFrames"]+overlap_start-clip["startFrame"],"gain":track["gain"],"pan":track["pan"],"outputBus":track["outputBus"],"sends":track["sends"],"automation":track["automation"],"fades":dict(clip.get("fades") or {}),"source":clip["source"]})
                regions[-1].update({"clipOffsetFrames":overlap_start-clip["startFrame"],"clipLengthFrames":clip["lengthFrames"]})
    regions.sort(key=lambda x:(x["renderStartFrame"],x["trackId"],x["clipId"]))
    return {"documentType":"org.upp.daw-render-plan","schemaVersion":1,"sessionId":session["sessionId"],"sessionRevision":session["revision"],"startFrame":start,"endFrame":end,"sampleRate":CANONICAL_RATE,"regions":regions,"bounded":True,"offline":True,"physicalOutputsArmed":False}

class DawSessionStore:
    def __init__(self,path:Path)->None:self.path=Path(path);self.history_path=self.path.with_suffix(".history.json");self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=RLock()
    def load(self)->dict[str,Any]:
        with self.lock:
            if not self.path.exists():return normalize_session({"sessionId":"default","tracks":[]})
            return normalize_session(json.loads(self.path.read_text("utf-8")))
    def save(self,value:dict[str,Any])->dict[str,Any]:
        result=normalize_session(value)
        with self.lock:
            if result["revision"]<=self.load()["revision"]:raise ValueError("DAW session revision must advance")
            fd,name=tempfile.mkstemp(prefix=".daw-",suffix=".json",dir=self.path.parent)
            try:
                with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(result,f,indent=2,sort_keys=True);f.write("\n");f.flush();os.fsync(f.fileno())
                os.replace(name,self.path)
            finally:
                if os.path.exists(name):os.unlink(name)
        return result

    def _history(self)->dict[str,Any]:
        if not self.history_path.exists():return {"undo":[],"redo":[]}
        value=json.loads(self.history_path.read_text("utf-8"));return {"undo":list(value.get("undo",[]))[-100:],"redo":list(value.get("redo",[]))[-100:]}

    def _write_history(self,value:dict[str,Any])->None:
        self.history_path.write_text(json.dumps(value,separators=(",",":")),encoding="utf-8")

    def edit(self,operation:dict[str,Any])->dict[str,Any]:
        with self.lock:
            before=self.load();after=deepcopy(before);op=str(operation.get("op",""));clip_id=str(operation.get("clipId",""));track=None;index=-1
            expected=operation.get("expectedRevision")
            if type(expected) is not int or expected!=before["revision"]:raise ValueError(f"DAW edit expected revision {before['revision']}")
            if op=="moveMany":
                self._move_many(after,operation)
                return self._commit_edit(before,after)
            for candidate in after["tracks"]:
                for position,clip in enumerate(candidate["clips"]):
                    if clip["clipId"]==clip_id:track=candidate;index=position;break
                if track:break
            if track is None:raise ValueError("clip not found")
            clip=track["clips"][index]
            if op=="trim":
                trim_start=max(0,int(operation.get("trimStartFrames",0)));trim_end=max(0,int(operation.get("trimEndFrames",0)))
                if trim_start+trim_end>=clip["lengthFrames"]:raise ValueError("trim removes complete clip")
                if "spanFrames" in clip["fades"]:clip["fades"]["offsetFrames"]+=trim_start
                clip["startFrame"]+=trim_start;clip["sourceOffsetFrames"]+=trim_start;clip["lengthFrames"]-=trim_start+trim_end
            elif op=="split":
                split=int(operation.get("splitFrame",0));relative=split-clip["startFrame"]
                if relative<=0 or relative>=clip["lengthFrames"]:raise ValueError("split must fall inside clip")
                clip["fades"].setdefault("spanFrames",clip["lengthFrames"])
                clip["fades"].setdefault("offsetFrames",0)
                right=deepcopy(clip);right["clipId"]=str(operation.get("newClipId",clip_id+"-split"))[:128];right["startFrame"]=split;right["sourceOffsetFrames"]+=relative;right["lengthFrames"]-=relative;clip["lengthFrames"]=relative;track["clips"].insert(index+1,right)
                right["fades"]["offsetFrames"]+=relative
            elif op=="fade":
                fade_in=max(0,int(operation.get("fadeInFrames",0)));fade_out=max(0,int(operation.get("fadeOutFrames",0)))
                if fade_in+fade_out>clip["lengthFrames"]:raise ValueError("combined fades exceed clip length")
                clip["fades"]={"inFrames":fade_in,"outFrames":fade_out,"curve":str(operation.get("curve","equal-power"))}
            elif op=="move":
                start=operation.get("startFrame");snap=operation.get("snapFrames",1)
                if type(start) is not int or start<0:raise ValueError("move startFrame must be a non-negative integer")
                if type(snap) is not int or snap<1 or snap>CANONICAL_RATE*60:raise ValueError("snapFrames must be an integer from 1 frame through one minute")
                start=((start+snap//2)//snap)*snap
                target_id=str(operation.get("targetTrackId",track["trackId"]))
                target=next((candidate for candidate in after["tracks"] if candidate["trackId"]==target_id),None)
                if target is None:raise ValueError("target track not found")
                source_type=clip["source"]["type"]
                if (source_type=="audio-file" and target["kind"] not in {"audio","aux"}) or (source_type=="midi-sequence" and target["kind"]!="midi"):
                    raise ValueError("clip source is incompatible with target track")
                clip["startFrame"]=start
                if target is not track:
                    track["clips"].pop(index);target["clips"].append(clip)
                target["clips"].sort(key=lambda item:(item["startFrame"],item["clipId"]))
            elif op=="resize":
                start=operation.get("startFrame");end=operation.get("endFrame");snap=operation.get("snapFrames",1)
                if type(start) is not int or type(end) is not int:raise ValueError("resize boundaries must be JSON integers")
                if type(snap) is not int or snap<1 or snap>CANONICAL_RATE*60:raise ValueError("snapFrames must be an integer from 1 frame through one minute")
                start=((start+snap//2)//snap)*snap;end=((end+snap//2)//snap)*snap
                old_start=clip["startFrame"];old_end=old_start+clip["lengthFrames"]
                if start<old_start or end>old_end or end<=start:raise ValueError("resize may trim within the current clip only")
                trim_start=start-old_start
                if "spanFrames" in clip["fades"]:clip["fades"]["offsetFrames"]+=trim_start
                clip["startFrame"]=start;clip["sourceOffsetFrames"]+=trim_start;clip["lengthFrames"]=end-start
            else:raise ValueError("unsupported DAW edit")
            return self._commit_edit(before,after)

    def _move_many(self,session:dict[str,Any],operation:dict[str,Any])->None:
        raw_ids=operation.get("clipIds")
        if not isinstance(raw_ids,list) or not 2<=len(raw_ids)<=256 or any(not isinstance(value,str) or not value for value in raw_ids):raise ValueError("moveMany requires 2 through 256 clip ids")
        clip_ids=list(dict.fromkeys(raw_ids))
        if len(clip_ids)!=len(raw_ids):raise ValueError("moveMany clip ids must be unique")
        delta=operation.get("deltaFrames");snap=operation.get("snapFrames",1)
        if type(delta) is not int or abs(delta)>CANONICAL_RATE*60*60:raise ValueError("deltaFrames must be an integer within one hour")
        if type(snap) is not int or snap<1 or snap>CANONICAL_RATE*60:raise ValueError("snapFrames must be an integer from 1 frame through one minute")
        clips={clip["clipId"]:clip for track in session["tracks"] for clip in track["clips"] if clip["clipId"] in clip_ids}
        if len(clips)!=len(clip_ids):raise ValueError("group clip not found")
        anchor=min(clips.values(),key=lambda clip:(clip["startFrame"],clip["clipId"]))
        snapped=((anchor["startFrame"]+delta+snap//2)//snap)*snap;applied=snapped-anchor["startFrame"]
        if any(clip["startFrame"]+applied<0 for clip in clips.values()):raise ValueError("group move would cross timeline start")
        for clip in clips.values():clip["startFrame"]+=applied
        for track in session["tracks"]:track["clips"].sort(key=lambda item:(item["startFrame"],item["clipId"]))

    def _commit_edit(self,before:dict[str,Any],after:dict[str,Any])->dict[str,Any]:
        after["revision"]=before["revision"]+1;history=self._history();history["undo"].append(before);history["undo"]=history["undo"][-100:];history["redo"]=[]
        saved=self.save(after);self._write_history(history);return saved

    def marker_edit(self,operation:dict[str,Any])->dict[str,Any]:
        with self.lock:
            before=self.load();expected=operation.get("expectedRevision")
            if type(expected) is not int or expected!=before["revision"]:raise ValueError(f"marker edit expected revision {before['revision']}")
            after=deepcopy(before);action=str(operation.get("action",""));marker_id=str(operation.get("markerId","")).strip()[:128]
            index=next((i for i,marker in enumerate(after["markers"]) if marker["markerId"]==marker_id),-1)
            if action=="add":
                if not marker_id or index>=0 or len(after["markers"])>=1024:raise ValueError("marker id must be unique and capacity available")
                frame=operation.get("frame");kind=str(operation.get("kind","note"))
                if type(frame) is not int or frame<0:raise ValueError("marker frame must be a non-negative integer")
                if kind not in {"note","section","cue"}:raise ValueError("unsupported marker kind")
                name=str(operation.get("name",marker_id)).strip()[:128] or marker_id
                after["markers"].append({"markerId":marker_id,"frame":frame,"name":name,"kind":kind})
            elif action=="move":
                if index<0:raise ValueError("marker not found")
                frame=operation.get("frame");snap=operation.get("snapFrames",1)
                if type(frame) is not int or frame<0 or type(snap) is not int or not 1<=snap<=CANONICAL_RATE*60:raise ValueError("marker move frame and snapFrames are invalid")
                after["markers"][index]["frame"]=((frame+snap//2)//snap)*snap
            elif action=="delete":
                if index<0:raise ValueError("marker not found")
                after["markers"].pop(index)
            else:raise ValueError("unsupported marker action")
            after["markers"].sort(key=lambda marker:(marker["frame"],marker["markerId"]))
            return self._commit_edit(before,after)

    def automation_edit(self,operation:dict[str,Any])->dict[str,Any]:
        with self.lock:
            before=self.load();expected=operation.get("expectedRevision")
            if type(expected) is not int or expected!=before["revision"]:raise ValueError(f"automation edit expected revision {before['revision']}")
            after=deepcopy(before);track_id=str(operation.get("trackId",""));track=next((item for item in after["tracks"] if item["trackId"]==track_id),None)
            if track is None:raise ValueError("automation track not found")
            action=str(operation.get("action",""));point_id=str(operation.get("pointId","")).strip()[:128];index=next((i for i,p in enumerate(track["automation"]) if p["pointId"]==point_id),-1)
            if action=="upsert":
                frame=operation.get("frame");value=operation.get("value");parameter=str(operation.get("parameter","volume"))
                if not point_id or parameter!="volume" or type(frame) is not int or frame<0 or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=2:raise ValueError("invalid volume automation point")
                collision=next((p for p in track["automation"] if p["parameter"]==parameter and p["frame"]==frame and p["pointId"]!=point_id),None)
                if collision:raise ValueError("automation position already has a point")
                point={"pointId":point_id,"parameter":parameter,"frame":frame,"value":float(value),"interpolation":"linear"}
                if index<0:
                    if len(track["automation"])>=4096:raise ValueError("automation point capacity reached")
                    track["automation"].append(point)
                else:track["automation"][index]=point
            elif action=="delete":
                if index<0:raise ValueError("automation point not found")
                track["automation"].pop(index)
            else:raise ValueError("unsupported automation action")
            track["automation"].sort(key=lambda point:(point["parameter"],point["frame"],point["pointId"]))
            return self._commit_edit(before,after)

    def undo(self)->dict[str,Any]:return self._restore("undo","redo")
    def redo(self)->dict[str,Any]:return self._restore("redo","undo")
    def _restore(self,source:str,target:str)->dict[str,Any]:
        with self.lock:
            history=self._history()
            if not history[source]:raise ValueError(f"nothing to {source}")
            current=self.load();restored=history[source].pop();history[target].append(current);restored["revision"]=current["revision"]+1
            saved=self.save(restored);self._write_history(history);return saved
