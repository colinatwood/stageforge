from __future__ import annotations

import hashlib, math, struct, wave
from pathlib import Path
from typing import Any

MAX_MEDIA_BYTES=2*1024*1024*1024;MAX_PEAK_BUCKETS=4096

def _decode_pcm(data:bytes,width:int)->list[float]:
    if width==1:return [(value-128)/128.0 for value in data]
    if width==2:return [value/32768.0 for value in struct.unpack("<"+"h"*(len(data)//2),data)]
    if width==3:
        values=[]
        for i in range(0,len(data)-2,3):
            raw=int.from_bytes(data[i:i+3],"little",signed=False);raw=raw-(1<<24) if raw&(1<<23) else raw;values.append(raw/8388608.0)
        return values
    if width==4:return [value/2147483648.0 for value in struct.unpack("<"+"i"*(len(data)//4),data)]
    raise ValueError("unsupported PCM sample width")

def inspect_wav(path:Path,*,peak_buckets:int=512)->dict[str,Any]:
    path=Path(path).resolve();size=path.stat().st_size
    if size>MAX_MEDIA_BYTES:raise ValueError("media file exceeds 2 GiB inspection bound")
    peak_buckets=max(1,min(int(peak_buckets),MAX_PEAK_BUCKETS))
    digest=hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda:source.read(1024*1024),b""):digest.update(block)
    with wave.open(str(path),"rb") as wav:
        channels=wav.getnchannels();rate=wav.getframerate();frames=wav.getnframes();width=wav.getsampwidth()
        if channels<1 or channels>64 or rate<8000 or rate>768000:raise ValueError("WAV format is outside platform bounds")
        bucket_frames=max(1,math.ceil(frames/peak_buckets));peaks=[]
        while len(peaks)<peak_buckets:
            raw=wav.readframes(bucket_frames)
            if not raw:break
            samples=_decode_pcm(raw,width);channel_peaks=[]
            for channel in range(channels):
                values=samples[channel::channels];channel_peaks.append({"min":min(values,default=0.0),"max":max(values,default=0.0)})
            peaks.append(channel_peaks)
    return {"documentType":"org.upp.daw-media","schemaVersion":1,"contentHash":"sha256:"+digest.hexdigest(),"uri":path.as_uri(),"container":"wav","encoding":f"pcm-s{width*8}" if width>1 else "pcm-u8","channels":channels,"sourceSampleRate":rate,"sourceFrames":frames,"canonicalFrames":round(frames*192000/rate),"waveform":{"bucketFrames":bucket_frames,"buckets":peaks},"readOnlySource":True,"physicalOutputsArmed":False}

def resolve_media_path(root:Path,relative:str)->Path:
    root=Path(root).resolve();candidate=(root/relative).resolve()
    if candidate!=root and root not in candidate.parents:raise PermissionError("media path escapes configured root")
    if not candidate.is_file():raise FileNotFoundError(candidate)
    return candidate
