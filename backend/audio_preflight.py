"""Explicit Linux hardware-PCM constraint query; never configures or starts I/O."""
import ctypes as C
import errno
import platform
import re


def validate_request(data):
    if not isinstance(data, dict):
        raise ValueError("audio preflight requires an object")
    address = data.get("address")
    if not isinstance(address, str) or not re.fullmatch(r"hw:[0-9]{1,3},[0-9]{1,3}", address):
        raise ValueError("address must be a numeric hardware PCM, e.g. hw:0,0")
    direction = data.get("direction", "playback")
    fmt = data.get("format", "FLOAT_LE")
    if direction not in ("playback", "capture") or fmt not in ("FLOAT_LE", "S32_LE", "S24_3LE", "S16_LE"):
        raise ValueError("unsupported direction or sample format")
    values = {}
    for key, default, low, high in (("sampleRate", 48000, 8000, 384000), ("channels", 2, 1, 32), ("periodFrames", 256, 16, 8192)):
        value = data.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be an integer from {low} to {high}")
        values[key] = value
    return {"address": address, "direction": direction, "format": fmt, **values}


class AlsaProbe:
    def __init__(self):
        self.lib = C.CDLL("libasound.so.2")
        p, i, u = C.c_void_p, C.c_int, C.c_uint
        specs = {
            "snd_pcm_open": ([C.POINTER(p), C.c_char_p, i, i], i),
            "snd_pcm_close": ([p], i),
            "snd_pcm_hw_params_malloc": ([C.POINTER(p)], i),
            "snd_pcm_hw_params_free": ([p], None),
            "snd_pcm_hw_params_any": ([p, p], i),
            "snd_pcm_hw_params_set_access": ([p, p, i], i),
            "snd_pcm_hw_params_set_format": ([p, p, i], i),
            "snd_pcm_hw_params_set_channels": ([p, p, u], i),
            "snd_pcm_hw_params_set_rate": ([p, p, u, i], i),
            "snd_pcm_hw_params_set_period_size": ([p, p, C.c_ulong, i], i),
            "snd_pcm_format_value": ([C.c_char_p], i),
        }
        for name, (args, result) in specs.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, result

    def check(self, request):
        pcm, params = C.c_void_p(), C.c_void_p()
        lib = self.lib
        result = lib.snd_pcm_open(C.byref(pcm), request["address"].encode("ascii"),
                                  0 if request["direction"] == "playback" else 1, 1)
        if result < 0:
            return "open", result
        try:
            result = lib.snd_pcm_hw_params_malloc(C.byref(params))
            if result < 0:
                return "allocate", result
            try:
                steps = [
                    ("constraints", lambda: lib.snd_pcm_hw_params_any(pcm, params)),
                    ("access", lambda: lib.snd_pcm_hw_params_set_access(pcm, params, 3)),
                    ("format", lambda: lib.snd_pcm_hw_params_set_format(pcm, params, lib.snd_pcm_format_value(request["format"].encode("ascii")))),
                    ("channels", lambda: lib.snd_pcm_hw_params_set_channels(pcm, params, request["channels"])),
                    ("sampleRate", lambda: lib.snd_pcm_hw_params_set_rate(pcm, params, request["sampleRate"], 0)),
                    ("periodFrames", lambda: lib.snd_pcm_hw_params_set_period_size(pcm, params, request["periodFrames"], 0)),
                ]
                for stage, call in steps:
                    result = call()
                    if result < 0:
                        return stage, result
                return "complete", 0
            finally:
                lib.snd_pcm_hw_params_free(params)
        finally:
            lib.snd_pcm_close(pcm)


def audio_preflight(data, *, system=None, probe_factory=AlsaProbe):
    request = validate_request(data)
    report = {"documentType": "org.upp.audio-preflight", "schemaVersion": 1,
              "request": request, "status": "unavailable", "supported": None,
              "physicalOutputsArmed": False, "streamStarted": False,
              "qualification": "hardware-tests-required", "stage": None, "errorCode": None,
              "nextAction": "Use a Linux ALSA host for this preflight.",
              "scope": "Requested interleaved PCM constraints only; stream open and runtime timing remain unverified"}
    if (system or platform.system()) != "Linux":
        return report
    try:
        stage, code = probe_factory().check(request)
    except (OSError, AttributeError):
        report["nextAction"] = "Install or repair the OS ALSA runtime; required library or symbols are unavailable."
        return report
    report.update(stage=stage, errorCode=code if code < 0 else None)
    if code >= 0:
        report.update(status="constraints-supported", supported=True,
                      nextAction="Explicitly configure the stream and verify its actual format and timing before use.")
    elif code == -errno.EBUSY:
        report.update(status="busy", nextAction="Release the PCM from its current owner, then retry.")
    elif code in (-errno.EACCES, -errno.EPERM):
        report.update(status="permission-denied", nextAction="Check device permissions for the server account.")
    elif code in (-errno.ENOENT, -errno.ENODEV):
        report.update(status="disconnected-or-missing", nextAction="Rescan devices and confirm the PCM address.")
    elif code == -errno.EINVAL and stage in ("access", "format", "channels", "sampleRate", "periodFrames"):
        report.update(status="constraints-unsupported", supported=False,
                      nextAction=f"The combined request failed at {stage}; revise the request and retry. No fallback was applied.")
    else:
        report.update(status="probe-error", nextAction="Inspect the ALSA error and retry; support remains unknown.")
    return report
