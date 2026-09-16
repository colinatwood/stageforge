# Sol backlog checkpoint 18 validation

Checkpoint 18 establishes the native real-time half of independent polyphonic streaming playback.

## Implemented contract

- Sixteen fixed voice slots each own an independent bounded block queue and playback cursor.
- Start, feed and stop operations are generation fenced.
- Feed sequence gaps and stale generations become explicit counters.
- One-shot terminal blocks complete only their voice; looping voices remain independently active.
- Starvation emits silence for only the affected voice and increments evidence once per render block.
- Output zero mixes the voices as a separate graph source.
- Blocks are capped at 256 stereo frames and queues are bounded to eight usable blocks per voice.
- Active-mask status supports later control-thread lifecycle reclamation.
- Disk I/O, decoding, allocation, locks and hardware activation stay outside the callback.

## Remaining boundary

Streaming bank triggers still use the shared arrangement producer. Service-thread WAV feeding, prebuffer policy, backpressure retry, cancellation and completed-slot reclamation remain required before the banks are genuinely polyphonic end to end.

## Recorded result

- 404 Python tests passed.
- Native streaming/transaction tests and current-ABI smoke passed.
- Frontend syntax and production-panel tests passed.
- OpenAPI and all 116 JSON schemas parsed successfully.

The Python suite's separate sanitizer prerequisite probe cannot find `cmake` and `ctest` in its process environment, so that environment-gated release check was not counted as executed.
