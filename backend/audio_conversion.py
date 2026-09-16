"""Explicit conversion policy between device PCM and the canonical audio graph."""
from __future__ import annotations

FORMATS={"FLOAT_LE","S32_LE","S24_3LE","S16_LE"}


def audio_conversion_plan(device:dict,policy:dict|None,*,direction:str)->dict:
    if direction not in {"playback","capture"}:raise ValueError("conversion direction must be playback or capture")
    try:rate=int(device["sampleRate"]);channels=int(device["channels"]);sample_format=str(device["format"])
    except (KeyError,TypeError,ValueError) as exc:raise ValueError("device parameters require sampleRate, channels and format") from exc
    if not 8000<=rate<=384000 or not 1<=channels<=32 or sample_format not in FORMATS:raise ValueError("invalid device audio parameters")
    value={} if policy is None else policy
    if not isinstance(value,dict):raise ValueError("conversionPolicy must be an object")
    conversions=[];flags=0
    if rate!=192000:
        if value.get("sampleRate")!="bounded-sinc":raise ValueError("sample-rate conversion requires conversionPolicy.sampleRate=bounded-sinc")
        conversions.append({"kind":"sample-rate","from":rate if direction=="capture" else 192000,"to":192000 if direction=="capture" else rate,"algorithm":"bounded-sinc"});flags|=1
    if sample_format!="FLOAT_LE":
        if value.get("sampleFormat")!="normalize-integer":raise ValueError("integer PCM conversion requires conversionPolicy.sampleFormat=normalize-integer")
        conversions.append({"kind":"sample-format","from":sample_format if direction=="capture" else "FLOAT_LE","to":"FLOAT_LE" if direction=="capture" else sample_format,"algorithm":"signed-normalization"});flags|=4
    if channels!=2:
        required="mono-to-stereo" if direction=="capture" and channels==1 else ("stereo-to-mono" if direction=="playback" and channels==1 else "explicit-matrix")
        if value.get("channels")!=required:raise ValueError(f"channel conversion requires conversionPolicy.channels={required}")
        channel_conversion={"kind":"channels","from":channels if direction=="capture" else 2,"to":2 if direction=="capture" else channels,"algorithm":required}
        if required=="explicit-matrix":
            channel_conversion["matrix"]={"canonicalLeft":0,"canonicalRight":1,"additionalDeviceChannels":"silence-on-playback-ignore-on-capture"}
        elif required=="stereo-to-mono":
            channel_conversion["matrix"]={"mono":"0.5*left+0.5*right"}
        elif required=="mono-to-stereo":
            channel_conversion["matrix"]={"left":"mono","right":"mono"}
        conversions.append(channel_conversion);flags|=2
    return {"documentType":"org.upp.audio-conversion-plan","schemaVersion":1,"direction":direction,"canonical":{"sampleRate":192000,"format":"FLOAT_LE","channels":2},"device":{"sampleRate":rate,"format":sample_format,"channels":channels},"requiresConversion":bool(conversions),"conversions":conversions,"nativeConversionFlags":flags,"upscalingRestoresMissingBandwidth":False,"approved":True,"physicalOutputsArmed":False}
