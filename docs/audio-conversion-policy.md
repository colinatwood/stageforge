# Audio conversion policy and configured parameters

The internal graph remains stereo planar float32 at 192 kHz. A lower-rate or
integer source can be normalized into that domain, but conversion does not restore
bandwidth or detail absent from the source.

`POST /api/v1/hardware/audio-conversion-plan` accepts the device tuple, direction,
and explicit policy choices. For example:

```json
{
  "direction": "capture",
  "device": {"sampleRate": 48000, "format": "S24_3LE", "channels": 1},
  "conversionPolicy": {
    "sampleRate": "bounded-sinc",
    "sampleFormat": "normalize-integer",
    "channels": "mono-to-stereo"
  }
}
```

Each difference needs its own choice. Rate conversion uses `bounded-sinc`; integer
PCM uses `normalize-integer`; channel choices are `mono-to-stereo`,
`stereo-to-mono`, or `explicit-matrix` where applicable. An exact 192 kHz
FLOAT_LE stereo tuple requires no conversion policy.

Physical ALSA activation currently supports FLOAT_LE and up to stereo at the native
boundary. The wider planner vocabulary defines how future integer and multichannel
adapters must request conversion rather than silently enabling it.

After `snd_pcm_set_params`, the Linux playback and capture adapters query
`snd_pcm_hw_params_current` and report the driver's configured sample rate, period,
channel count, and format. Status retains the requested values separately. If the
query fails or returns values outside engine bounds, the stream does not start.
The native activation command also refuses a configured rate or channel difference
unless the matching policy flag was supplied.

Preflight and configured status answer different questions: preflight checks an
exact tuple without applying it; configured status records the values chosen after
the driver accepted configuration. Availability and timing still require hardware
qualification.
