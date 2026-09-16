from __future__ import annotations
import os,tempfile,wave
from pathlib import Path
from typing import Any
from daw_session import CANONICAL_RATE,render_plan
from durable_filesystem import publish_hardlink,unlink_and_sync

def playback_prefetch_plan(session:dict[str,Any],playhead_frame:int,*,lookahead_frames:int=384000)->dict[str,Any]:
    lookahead=max(1024,min(int(lookahead_frames),CANONICAL_RATE*10));plan=render_plan(session,max(0,int(playhead_frame)),max(0,int(playhead_frame))+lookahead)
    requests=[{"clipId":r["clipId"],"source":r["source"],"sourceStartFrame":r["sourceStartFrame"],"frames":r["renderFrames"]} for r in plan["regions"]]
    return {"documentType":"org.upp.daw-playback-prefetch","schemaVersion":1,"playheadFrame":max(0,int(playhead_frame)),"lookaheadFrames":lookahead,"requests":requests,"diskIoInAudioCallback":False,"missingMediaPolicy":"silence-and-report","physicalOutputsArmed":False}

class RecordingSpool:
    """Crash-safe WAV spool. An authenticated capture adapter owns actual input arming."""
    def __init__(self,root:Path)->None:self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self._wave=None;self._temp:Path|None=None;self._frames=0;self._dropouts=[]
    def begin(self,take_id:str,*,channels:int=2,sample_rate:int=CANONICAL_RATE,acknowledge_physical_input:bool=False)->dict[str,Any]:
        if not acknowledge_physical_input:raise PermissionError("recording requires explicit physical-input acknowledgement")
        if self._temp is not None:raise RuntimeError("recording already active or awaiting finalization")
        self._seal_failed=False
        fd,name=tempfile.mkstemp(prefix=f".{take_id}-",suffix=".partial.wav",dir=self.root);os.close(fd);self._temp=Path(name);self._wave=wave.open(name,"wb");self._wave.setnchannels(channels);self._wave.setsampwidth(4);self._wave.setframerate(sample_rate);self._frames=0;self._dropouts=[]
        return {"takeId":take_id,"state":"recording","physicalInputArmed":True,"physicalOutputsArmed":False}
    def append_s32(self,interleaved:bytes,frames:int)->None:
        if not self._wave:raise RuntimeError("recording inactive")
        if type(frames) is not int or frames<0 or len(interleaved)!=frames*self._wave.getnchannels()*4:
            raise ValueError("PCM byte count must match frame count and channel count")
        self._wave.writeframesraw(interleaved);self._frames+=int(frames)
    def dropout(self,start_frame:int,frames:int)->None:self._dropouts.append({"startFrame":int(start_frame),"frames":int(frames)})
    def finish(self,file_name:str)->dict[str,Any]:
        if not self._temp:raise RuntimeError("recording inactive")
        if self._seal_failed:raise RuntimeError("recording header finalization failed; abort the pending take")
        target=self.root/Path(file_name).name
        if target==self._temp:raise ValueError("recording output must differ from the partial file")
        if self._wave:
            try:self._wave.close()
            except Exception:
                self._seal_failed=True
                raise
            self._wave=None
        with self._temp.open("rb") as completed:os.fsync(completed.fileno())
        publish_hardlink(self._temp,target)  # Non-replacing publication + parent-directory durability.
        cleanup_pending=not unlink_and_sync(self._temp)
        self._temp=None
        return {"state":"complete","path":str(target),"frames":self._frames,"dropouts":self._dropouts[:1024],"dropoutFree":not self._dropouts,"atomicCompletion":True,"directoryDurable":True,"partialCleanupPending":cleanup_pending,"physicalInputArmed":False,"physicalOutputsArmed":False}
    def abort(self)->None:
        if self._wave:self._wave.close();self._wave=None
        if self._temp and self._temp.exists():self._temp.unlink()
        self._temp=None
