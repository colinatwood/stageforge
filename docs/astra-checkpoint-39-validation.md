# Astra backlog checkpoint 39 validation

Checkpoint 39 closes the Linux **physical PCM conversion adapter** software gap. It does not claim conversion-quality or named-hardware qualification.

## Delivered

- Physical ALSA playback/capture may now request `FLOAT_LE`, `S16_LE`, packed `S24_3LE`, or `S32_LE` explicitly.
- Activation carries the requested device PCM format and channel count from the HTTP/runtime conversion policy through `NativeEngineClient` into the native stdio command and ALSA adapter.
- The legacy float-stereo stdio command shape is retained when no new format/channel conversion is requested.
- ALSA resolves sample-format IDs through the runtime `snd_pcm_format_value` symbol, preserving the dependency-free native build.
- Playback and capture allocate float and device-PCM buffers before stream start. PCM encode/decode performs no allocation in the ALSA I/O loops.
- Integer conversion sanitizes non-finite float values and saturates to the signed PCM range.
- The v1 channel matrix is explicit and deterministic:
  - capture mono duplicates to canonical L/R;
  - playback mono is `0.5 * left + 0.5 * right`;
  - multichannel playback maps canonical L/R to device channels 0/1 and silences additional channels;
  - multichannel capture maps device channels 0/1 to canonical L/R and ignores additional channels.
- Native activation still refuses rate, channel, or integer-format conversion unless its corresponding explicit conversion-policy flag is present.
- The existing canonical-audio C ABI and `audio-conversion-plan` schema already describe signed 16/24/32-bit formats and conversion flags, so this slice realizes the existing contract rather than inventing a new ABI surface.

## Focused evidence

A live native stdio exercise against the Linux ALSA `null` PCM configured:

- playback: 48 kHz, 4 channels, `S16_LE`, explicit rate/channel/sample-format conversion;
- capture: 48 kHz, 4 channels, packed `S24_3LE`, explicit rate/channel/sample-format conversion.

The engine reported the exact configured format/channel values for both streams. This is execution-path evidence using ALSA's virtual PCM, not converter-quality evidence for a named physical interface.

Native regressions cover integer encode/decode, sample-format parsing/byte widths, multichannel buffers, and optional ALSA integer/multichannel open/start behavior. Python regressions cover explicit conversion matrices, exact preflight format propagation, extended stdio command framing, and the live native client path when the ALSA null PCM is present.

## Release gate

- Fresh RT-qualification native build: **passed**.
- Native CTest: **2/2 passed**.
- Release Python suite: **516 tests passed**, zero test failures.
- Automation performance: **passed** (`4096` points, `8192` frames, binary block-entry search).
- JSON schema set: **117 parsed**; OpenAPI JSON parsed.
- Frontend JavaScript: **7 files passed** `node --check`.

## Still open

- `AUD-034`: measured conversion quality on real converters/interfaces. Noise, distortion, phase continuity and resampling quality remain unqualified.
- Windows and macOS physical audio negotiation/conversion adapters remain open.
- Named-hardware latency/dropout/soak and audible behavior remain stage-qualification work.
