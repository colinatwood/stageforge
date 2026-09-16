# Audio configuration preflight

Use Compatibility → Check an ALSA audio configuration to query one exact hardware
PCM request. This opt-in check briefly opens and closes the selected endpoint in
nonblocking mode. It never applies hardware parameters, starts playback/capture,
changes the desired configuration, or activates routes. An already-owned endpoint
may report busy. Do not run probes repeatedly during a live show.

POST `/api/v1/hardware/audio-preflight` accepts:

```json
{"address":"hw:0,0","direction":"playback","sampleRate":48000,"channels":2,"periodFrames":256,"format":"FLOAT_LE"}
```

Numeric `hw:card,device` addresses only; arbitrary ALSA plugin names are rejected.
Directions are playback/capture. Formats: FLOAT_LE, S32_LE, S24_3LE, S16_LE.
Ranges: rate 8000–384000, channels 1–32, period 16–8192 frames, all integers.
The server validates before loading ALSA. The address is on the server host.

The query refines one parameter space in order: interleaved access, format,
channels, exact rate and exact period. It does not combine independent range
checks into an unsupported Cartesian product. A failure at a later constraint
means the combined request failed, not that the parameter is universally absent.

| Result | Meaning |
| --- | --- |
| constraints-supported | ALSA accepted the requested constraint combination; stream readiness remains unverified |
| constraints-unsupported | ALSA rejected a requested constraint with EINVAL |
| busy | Another owner or device state prevented the query |
| permission-denied | Server account could not access the endpoint |
| disconnected-or-missing | Device/address was not available |
| unavailable | Unsupported OS, missing ALSA runtime, or required symbols missing |
| probe-error | Other failure; support remains unknown |

`supported` is true/false only for a successful constraint query or a specific
constraint rejection; otherwise null. Responses always state that this operation
did not arm outputs or start a stream. This does not describe unrelated live routes.

Physical ALSA activation now reruns this exact query immediately before selection
and native activation. Any unknown, busy or unsupported result blocks activation;
only `constraints-supported` proceeds. Virtual null output remains available for
software workflows. There is no silent fallback. Checkpoint 39 now wires explicit
`FLOAT_LE`, `S16_LE`, packed `S24_3LE` and `S32_LE` device formats plus mono/multichannel
channel matrices through the real Linux ALSA playback/capture adapters. Integer and
channel conversion still require their explicit `conversionPolicy` choices, and all
float/device PCM buffers are allocated before stream start. Configured rate, period,
channels and sample format are reported after open.

A successful query/configuration still cannot guarantee later availability or audio
quality; activation must handle unplug, permission changes and competing owners.
Noise/distortion/phase/resampling quality and physical 192 kHz/32-bit converter claims
require named-hardware measurement. Windows/macOS endpoint and conversion adapters
remain open.

Output and input recovery now have explicit `/recover` endpoints and UI buttons.
They require `acknowledgeRecovery` plus the existing physical signal acknowledgments,
refuse already-active streams, rescan through activation, and stop a newly opened
stream if an immediate post-activation scan no longer contains the selected endpoint.
Status reports the configured rate, period and channels returned by the native
stream state. These are configured values, not independent measurements of hardware.

Implementation reference (checked 2026-09-11):
https://www.alsa-project.org/alsa-doc/alsa-lib/group___p_c_m___h_w___params.html

Validation includes fixture-backed success/error/resource-cleanup tests and HTTP
validation rejection. No physical hardware or browser interaction was tested.
All 329 Python tests passed without skips against the existing qualification-enabled
engine build. Frontend syntax passed and all 106 JSON schemas parsed. ALSA query
symbols loaded on this Linux host without opening an endpoint. Native code and
ABI were not changed in this increment.

The activation integration raised the full software result to 340 Python tests,
all passing without skips against the existing qualification-enabled engine.
