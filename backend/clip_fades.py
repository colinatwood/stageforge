"""Shared clip-relative fade envelopes for playback and offline rendering."""
import math


def fade_envelope(region, relative_frame):
    fades = region.get("fades") or {}
    position = fades.get("offsetFrames", 0) + region.get("clipOffsetFrames", 0) + relative_frame
    length = fades.get("spanFrames", region.get("clipLengthFrames", region["renderFrames"]))
    fade_in = int(fades.get("inFrames", 0))
    fade_out = int(fades.get("outFrames", 0))
    level = 1.0
    if fade_in:
        level = min(level, (position + 1) / fade_in)
    if fade_out:
        level = min(level, (length - position) / fade_out)
    level = max(0.0, min(1.0, level))
    curve = fades.get("curve", "equal-power")
    if curve == "equal-power":
        return math.sin(level * math.pi / 2)
    if curve == "linear":
        return level
    raise ValueError("unsupported clip fade curve")
