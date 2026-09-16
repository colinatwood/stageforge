from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

from daw_production import OfflineRenderer
from daw_media import resolve_media_path
from daw_session import normalize_session


MAX_NATIVE_SAMPLER_ASSETS = 32
MAX_NATIVE_SAMPLER_FRAMES = 65_536


class SamplerPreloadRegistry:
    """Control-thread DAW clip decoder and native sampler registration fence."""

    def __init__(self, native: Any, media_root: Path) -> None:
        self.native = native
        self.media_root = Path(media_root)
        self.reader = OfflineRenderer(self.media_root)
        self._lock = RLock()
        self._assets: dict[tuple[str, bool], dict[str, Any]] = {}
        self._published_generations = 0
        self._failures = 0
        self._last_error: str | None = None

    def _clip(self, session: dict[str, Any], clip_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for track in session["tracks"]:
            for clip in track["clips"]:
                if clip["clipId"] == clip_id:
                    if clip["source"].get("type") != "audio-file":
                        raise ValueError("native sampler preload requires an audio-file clip")
                    return track, clip
        raise ValueError("mapped DAW clip no longer exists")

    def _source_identity(self, uri: str, expected: str) -> tuple[Path, str]:
        relative = uri[6:] if uri.startswith("media/") else uri
        path = resolve_media_path(self.media_root, relative)
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        actual = "sha256:" + digest.hexdigest()
        if expected and expected != actual:
            raise ValueError("sampler source content hash mismatch")
        return path, actual

    def preload(self, session_value: dict[str, Any], clip_id: str, *, looped: bool = False,
                choke_group: int = 0, crossfade_frames: int = 256) -> dict[str, Any]:
        if not getattr(self.native, "supports_sampler_voice_engine", False):
            raise RuntimeError("native sampler voice engine unavailable")
        session = normalize_session(session_value)
        clip_id = str(clip_id).strip()
        track, clip = self._clip(session, clip_id)
        frames = int(clip["lengthFrames"])
        if frames < 1 or frames > MAX_NATIVE_SAMPLER_FRAMES:
            raise ValueError(f"native sampler clips must contain 1..{MAX_NATIVE_SAMPLER_FRAMES} canonical frames")
        source = clip["source"]
        _, content_hash = self._source_identity(str(source.get("uri", "")), str(source.get("contentHash", "")))
        mode = "loop" if looped else "oneshot"
        signature = f"r{session['revision']}:{content_hash}:{clip['sourceOffsetFrames']}:{frames}:{mode}:{int(choke_group)}"
        key = (clip_id, looped)
        with self._lock:
            previous = self._assets.get(key)
            if previous and previous["signature"] == signature:
                return deepcopy(previous)
            if self._published_generations >= MAX_NATIVE_SAMPLER_ASSETS:
                raise RuntimeError("native sampler preload registry is full")
        try:
            left, right = self.reader._source_slice(str(source.get("uri", "")), int(clip["sourceOffsetFrames"]), frames)
            pan = max(-1.0, min(1.0, float(track.get("pan", 0.0))))
            gain = max(0.0, min(4.0, float(track.get("gain", 1.0))))
            gain_left = gain * math.sqrt((1.0 - pan) / 2.0)
            gain_right = gain * math.sqrt((1.0 + pan) / 2.0)
            fades = clip.get("fades") or {}
            fade_in = int(fades.get("inFrames", 0)); fade_out = int(fades.get("outFrames", 0))
            for index in range(frames):
                envelope = min(1.0, (index + 1) / fade_in) if fade_in else 1.0
                if fade_out:
                    envelope = min(envelope, (frames - index) / fade_out)
                left[index] = max(-1.0, min(1.0, left[index] * gain_left * envelope))
                right[index] = max(-1.0, min(1.0, right[index] * gain_right * envelope))
            crossfade = min(max(0, int(crossfade_frames)), frames // 2) if looped else 0
            native_resource_id = f"{clip_id}-{mode}-{hashlib.sha256(signature.encode()).hexdigest()[:16]}"
            self.native.sampler_load_pcm(native_resource_id, left, right, choke_group=max(0, min(255, int(choke_group))),
                                         looped=looped, loop_begin=0, loop_end=frames, crossfade_frames=crossfade)
            record = {
                "resourceId": clip_id, "nativeResourceId": native_resource_id, "mode": mode,
                "sessionRevision": session["revision"], "sourceContentHash": content_hash,
                "sourceOffsetFrames": int(clip["sourceOffsetFrames"]), "frames": frames,
                "chokeGroup": max(0, min(255, int(choke_group))), "loopCrossfadeFrames": crossfade,
                "signature": signature, "registered": True, "physicalOutputsArmed": False,
            }
            with self._lock:
                self._assets[key] = record; self._published_generations += 1; self._last_error = None
            return deepcopy(record)
        except Exception as exc:
            with self._lock:
                self._failures += 1; self._last_error = str(exc)
            raise

    def resolve(self, clip_id: str, looped: bool) -> dict[str, Any] | None:
        with self._lock:
            value = self._assets.get((str(clip_id), bool(looped)))
            return deepcopy(value) if value else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            assets = [deepcopy(value) for value in self._assets.values()]
            return {"documentType":"org.upp.sampler-preload-status", "schemaVersion":1,
                    "available": bool(getattr(self.native, "supports_sampler_voice_engine", False)),
                    "capacity": MAX_NATIVE_SAMPLER_ASSETS, "maximumFramesPerAsset": MAX_NATIVE_SAMPLER_FRAMES,
                    "registered": len(assets), "publishedGenerations": self._published_generations, "assets": assets, "failures": self._failures,
                    "lastError": self._last_error, "diskIoInAudioCallback": False, "physicalOutputsArmed": False}
