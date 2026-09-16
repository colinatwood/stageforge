from __future__ import annotations

import bisect,hashlib,json,math,os,random,shutil,struct,tempfile,time,wave
from copy import deepcopy
from pathlib import Path
from typing import Any
from daw_media import _decode_pcm,inspect_wav,resolve_media_path
from daw_session import CANONICAL_RATE,normalize_session,render_plan
from media_snapshot import MediaSnapshot
from clip_fades import fade_envelope
from plugin_host import validate_plugin_manifest
from staged_resources import StagedFile

def tempo_map(value:list[dict[str,Any]])->list[dict[str,Any]]:
    result=[];last_beat=-1.0
    for raw in value or [{"beat":0,"bpm":120,"numerator":4,"denominator":4}]:
        beat=float(raw.get("beat",0));bpm=float(raw.get("bpm",120));num=int(raw.get("numerator",4));den=int(raw.get("denominator",4))
        if beat<0 or beat<=last_beat or bpm<20 or bpm>400 or num<1 or num>32 or den not in {1,2,4,8,16,32}:raise ValueError("invalid tempo map")
        result.append({"beat":beat,"bpm":bpm,"numerator":num,"denominator":den});last_beat=beat
    if result[0]["beat"]!=0:raise ValueError("tempo map must begin at beat zero")
    return result

def beat_to_frame(points:list[dict[str,Any]],beat:float)->int:
    points=tempo_map(points);target=max(0.0,float(beat));seconds=0.0
    for i,p in enumerate(points):
        next_beat=points[i+1]["beat"] if i+1<len(points) else target
        covered=max(0.0,min(target,next_beat)-p["beat"]);seconds+=covered*60.0/p["bpm"]
        if target<next_beat:break
    return round(seconds*CANONICAL_RATE)

def automation_value(points:list[dict[str,Any]],frame:int,default:float)->float:
    ordered=sorted(({"frame":int(p["frame"]),"value":float(p["value"])} for p in points),key=lambda p:p["frame"])
    if not ordered or frame<ordered[0]["frame"]:return default
    for left,right in zip(ordered,ordered[1:]):
        if frame<=right["frame"]:
            ratio=(frame-left["frame"])/max(1,right["frame"]-left["frame"]);return left["value"]+(right["value"]-left["value"])*ratio
    return ordered[-1]["value"]

class PreparedAutomation:
    """Immutable automation lane prepared once for repeated render blocks."""
    def __init__(self,points,default=1.0):
        self.points=tuple(sorted(((int(p["frame"]),float(p["value"])) for p in points),key=lambda p:p[0]))
        self.frames=tuple(point[0] for point in self.points)
        self.default=float(default)
    def block(self,start,count):
        ordered=self.points;segment=max(0,bisect.bisect_left(self.frames,start)-1)
        for frame in range(start,start+count):
            if not ordered or frame<ordered[0][0]:
                yield self.default
                continue
            while segment+1<len(ordered) and frame>ordered[segment+1][0]:segment+=1
            if segment+1==len(ordered):yield ordered[-1][1]
            else:
                left,right=ordered[segment],ordered[segment+1]
                ratio=(frame-left[0])/max(1,right[0]-left[0])
                yield left[1]+(right[1]-left[1])*ratio

def automation_block(points, start, count, default=1.0):
    """Prepare points once per block; advance monotonically through segments."""
    yield from PreparedAutomation(points,default).block(start,count)

class MediaLibrary:
    def __init__(self,root:Path)->None:self.root=Path(root);self.objects=self.root/"objects";self.objects.mkdir(parents=True,exist_ok=True)
    def ingest(self,path:Path)->dict[str,Any]:
        source=Path(path).resolve();info=inspect_wav(source);digest=info["contentHash"].split(":",1)[1];target=self.objects/digest[:2]/f"{digest}.wav";target.parent.mkdir(parents=True,exist_ok=True)
        existed=target.exists()
        if existed:
            if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                raise ValueError("managed media hash mismatch")
        else:
            staged=StagedFile(target.parent,prefix=".media-",suffix="",resource_class="media-import",purpose="content-addressed-import");name=str(staged.path)
            try:
                shutil.copyfile(source,name)
                if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
                    raise ValueError("import source changed during copy")
                staged.publish(target)
            finally:
                staged.close()
        return {**info,"managedPath":str(target.relative_to(self.root)),"deduplicated":existed,"physicalOutputsArmed":False}
    def verify(self,relative:str,expected_hash:str)->dict[str,Any]:
        path=resolve_media_path(self.root,relative);actual="sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
        return {"path":relative,"expectedHash":expected_hash,"actualHash":actual,"verified":actual==expected_hash,"physicalOutputsArmed":False}

class TakeManager:
    def __init__(self,root:Path)->None:self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def prepare(self,track_id:str,start_frame:int,*,pre_roll_frames:int=0,punch_out_frame:int|None=None)->dict[str,Any]:
        take_id=f"take-{time.time_ns()}";return {"documentType":"org.upp.daw-recording-take","schemaVersion":1,"takeId":take_id,"trackId":track_id,"startFrame":max(0,int(start_frame)),"preRollFrames":max(0,int(pre_roll_frames)),"punchOutFrame":punch_out_frame,"state":"prepared","dropouts":[],"physicalInputArmed":False,"physicalOutputsArmed":False}
    def finalize(self,plan:dict[str,Any],relative_wav:str,dropouts:list[dict[str,Any]]|None=None)->dict[str,Any]:
        path=resolve_media_path(self.root,relative_wav);media=inspect_wav(path);return {**plan,"state":"complete","media":media,"dropouts":list(dropouts or [])[:1024],"dropoutFree":not dropouts,"physicalInputArmed":False,"physicalOutputsArmed":False}

class PluginCatalog:
    def __init__(self,path:Path)->None:self.path=Path(path);self.quarantine_path=self.path.with_suffix(".quarantine.json")
    def scan(self)->dict[str,Any]:
        quarantine=json.loads(self.quarantine_path.read_text()) if self.quarantine_path.exists() else {};plugins=[]
        if self.path.exists():
            for manifest in sorted(self.path.glob("*.json"))[:1024]:
                try:
                    value=validate_plugin_manifest(json.loads(manifest.read_text()));fmt=value["format"];pid=value["pluginId"]
                    plugins.append({"pluginId":pid,"format":fmt,"adapterExecutable":value.get("adapterExecutable"),"hostCompatible":True,"quarantined":pid in quarantine,"reason":quarantine.get(pid)})
                except Exception as exc:plugins.append({"pluginId":manifest.stem,"format":"unknown","quarantined":True,"reason":str(exc)})
        return {"plugins":plugins,"scanIsolated":True,"physicalOutputsArmed":False}
    def quarantine(self,plugin_id:str,reason:str)->None:
        value=json.loads(self.quarantine_path.read_text()) if self.quarantine_path.exists() else {};value[str(plugin_id)]=str(reason)[:512];self.quarantine_path.parent.mkdir(parents=True,exist_ok=True);self.quarantine_path.write_text(json.dumps(value,sort_keys=True))

class AutosaveStore:
    def __init__(self,root:Path)->None:self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def save(self,session:dict[str,Any])->dict[str,Any]:
        normalized=normalize_session(session);payload=json.dumps(normalized,sort_keys=True,separators=(",",":")).encode();digest=hashlib.sha256(payload).hexdigest();target=self.root/f"r{normalized['revision']}-{digest[:12]}.json";target.write_bytes(payload)
        files=sorted(self.root.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True)
        for stale in files[20:]:stale.unlink()
        return {"path":str(target),"revision":normalized["revision"],"sha256":digest,"recoverable":True,"physicalOutputsArmed":False}

class OfflineRenderer:
    def __init__(self,media_root:Path)->None:self.media_root=Path(media_root)
    def verify_plan_media(self,plan:dict[str,Any])->None:
        checked=set()
        for region in plan["regions"]:
            source=region["source"];expected=source.get("contentHash")
            if source.get("type")!="audio-file" or not expected:continue
            uri=str(source.get("uri",""));key=(uri,expected)
            if key in checked:continue
            path=resolve_media_path(self.media_root,uri[6:] if uri.startswith("media/") else uri)
            digest=hashlib.sha256()
            with path.open("rb") as media:
                while chunk:=media.read(65536):digest.update(chunk)
            if "sha256:"+digest.hexdigest()!=expected:raise ValueError("session media hash mismatch: "+uri)
            checked.add(key)
    def _source(self,uri:str)->tuple[list[float],list[float],int]:
        relative=uri[6:] if uri.startswith("media/") else uri;path=resolve_media_path(self.media_root,relative)
        with wave.open(str(path),"rb") as w:
            channels=w.getnchannels();rate=w.getframerate();samples=_decode_pcm(w.readframes(w.getnframes()),w.getsampwidth());left=samples[0::channels];right=samples[1::channels] if channels>1 else list(left)
        return left,right,rate
    def _source_slice(self,uri:str,start:int,count:int)->tuple[list[float],list[float]]:
        relative=uri[6:] if uri.startswith("media/") else uri;path=resolve_media_path(self.media_root,relative)
        with wave.open(str(path),"rb") as w:
            channels=w.getnchannels();rate=w.getframerate();source_start=max(0,(start*rate)//CANONICAL_RATE-1);source_end=((start+count)*rate+CANONICAL_RATE-1)//CANONICAL_RATE+2;w.setpos(min(source_start,w.getnframes()));samples=_decode_pcm(w.readframes(max(0,source_end-source_start)),w.getsampwidth());left=samples[0::channels];right=samples[1::channels] if channels>1 else list(left)
        return self._resample(left,rate,count,start,source_origin=source_start),self._resample(right,rate,count,start,source_origin=source_start)
    @staticmethod
    def _resample(data:list[float],rate:int,count:int,start:int,*,source_origin:int=0)->list[float]:
        result=[]
        for i in range(count):
            lo,remainder=divmod((start+i)*rate,CANONICAL_RATE);lo-=source_origin;fraction=remainder/CANONICAL_RATE
            a=data[lo] if 0<=lo<len(data) else 0.0;b=data[lo+1] if 0<=lo+1<len(data) else a;result.append(a+(b-a)*fraction)
        return result
    def render(self,session:dict[str,Any],output:Path,start_frame:int,end_frame:int,*,bits:int=24,seed:int=0)->dict[str,Any]:
        if bits not in {16,24,32}:raise ValueError("export bits must be 16, 24, or 32")
        snapshot=MediaSnapshot(self.media_root,render_plan(session,start_frame,end_frame),purpose="offline-render")
        try:return OfflineRenderer(snapshot.root)._render_snapshot(snapshot.plan,output,start_frame,end_frame,bits=bits,seed=seed)
        finally:snapshot.close()
    def _render_snapshot(self,plan,output,start_frame,end_frame,*,bits,seed):
        frames=end_frame-start_frame
        required=max(1024*1024,frames*2*(bits//8)+65536)
        if shutil.disk_usage(output.parent if output.parent.exists() else output.parent.parent).free<required:raise OSError("insufficient disk space for bounded render")
        source_hashes=sorted({r["source"].get("contentHash") for r in plan["regions"] if r["source"].get("contentHash")});rng=random.Random(seed);scale=(1<<(bits-1))-1;ceiling=10**(-1/20);limiter=1.0;peak=0.0;block_size=1024;output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);staged=StagedFile(output.parent,prefix=".render-",suffix=".wav",resource_class="render-output",purpose="offline-render-publication");temp_name=str(staged.path)
        volume_curves={id(region):PreparedAutomation([p for p in region.get("automation",[]) if p.get("parameter")=="volume"]) for region in plan["regions"]}
        try:
            with wave.open(temp_name,"wb") as w:
                w.setnchannels(2);w.setsampwidth(bits//8);w.setframerate(CANONICAL_RATE)
                for block_start in range(start_frame,end_frame,block_size):
                    count=min(block_size,end_frame-block_start);left=[0.0]*count;right=[0.0]*count
                    for region in plan["regions"]:
                        begin=max(block_start,region["renderStartFrame"]);finish=min(block_start+count,region["renderStartFrame"]+region["renderFrames"])
                        if finish<=begin or region["source"].get("type")!="audio-file":continue
                        amount=finish-begin;relative=begin-region["renderStartFrame"];sl,sr=self._source_slice(str(region["source"].get("uri","")),region["sourceStartFrame"]+relative,amount);pan=max(-1,min(1,region["pan"]));gl=region["gain"]*math.sqrt((1-pan)/2);gr=region["gain"]*math.sqrt((1+pan)/2);fades=region.get("fades") or {};fi=int(fades.get("inFrames",0));fo=int(fades.get("outFrames",0))
                        for i,automated in enumerate(volume_curves[id(region)].block(begin,amount)):
                            envelope=fade_envelope(region,relative+i)
                            destination=begin-block_start+i;left[destination]+=sl[i]*gl*envelope*automated;right[destination]+=sr[i]*gr*envelope*automated
                    payload=bytearray()
                    for l,r in zip(left,right):
                        frame_peak=max(abs(l),abs(r));peak=max(peak,frame_peak);limiter=min(limiter,ceiling/frame_peak) if frame_peak>ceiling else min(1.0,limiter+.002*(1-limiter))
                        for value in (l,r):
                            finite=value if math.isfinite(value) else 0.0;dither=(rng.random()-rng.random())/scale if bits<32 else 0;integer=round(max(-1,min(1,finite*limiter+dither))*scale);payload.extend(integer.to_bytes(bits//8,"little",signed=True))
                    w.writeframesraw(bytes(payload))
            staged.publish(output)
        finally:
            staged.close()
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        return {"documentType":"org.upp.daw-render-receipt","schemaVersion":1,"sessionId":plan["sessionId"],"sessionRevision":plan["sessionRevision"],"output":str(output),"outputSha256":digest,"sourceHashes":source_hashes,"sampleRate":CANONICAL_RATE,"bits":bits,"frames":frames,"peak":peak,"limiterGain":limiter,"blockFrames":block_size,"boundedMemory":True,"atomicCompletion":True,"dither":"tpdf" if bits<32 else "none","deterministicSeed":seed,"physicalOutputsArmed":False}
