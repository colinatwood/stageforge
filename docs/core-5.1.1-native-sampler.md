# Core 5.1.1 native sampler

Core 5.1.1 adds the bounded polyphonic voice engine required before sampler and looper controller mappings can become native execution. It processes immutable planar float32 assets in the canonical 192 kHz domain and owns no physical-output authority.

## Real-time contract

- The registering adapter owns immutable sample memory for the engine lifetime. Registration never transfers or copies sample storage.
- The Show Time owner sends trigger, stop-sample and stop-all commands through a bounded SPSC queue. The audio callback is the sole voice-state owner.
- The callback performs no allocation, locking, file access, discovery or format decoding.
- The reference capacity is 64 voices, 32 registered assets and 1,024 queued commands.
- Saturation steals the oldest active voice deterministically. Its replacement starts only after the fixed 64-frame release, avoiding a discontinuous cut.
- Choke groups release all active voices in the same group. Every voice has a fixed 32-frame attack and 64-frame release.
- Loops use an equal-power crossfade across the declared tail/head overlap. Invalid loop ranges are rejected during registration.

## MIDI and Show Time

Native mappings now carry a stable `resource_id`. `sample.trigger`, `loop.toggle` and `loop.clear` become typed sampler Show Events after the same beat quantization and optional master-key correction used by other learned actions. The `ShowExecutionLoop` remains the sole ordering authority; dispatch submits a bounded sampler command and records it in `CoreJournal`.

Only assets already registered in the sampler are eligible for this native path. The Python client exposes bounded development PCM staging, capped at 65,536 canonical frames per asset. Production streaming banks, long DAW clip preload and generation-fenced asset replacement remain provider work; the platform does not claim they are complete.

## Development protocol

- `SAMPLER_LOAD_BEGIN <sample-id> <frames> <choke-group> <looped> <loop-begin> <loop-end> <crossfade-frames>`
- `SAMPLER_LOAD_PCM <offset> <frames> <interleaved-float32-hex>`
- `SAMPLER_LOAD_COMMIT`
- `SAMPLER_TRIGGER <event-id> <show-ns> <sample-id> <velocity> <note>`
- `SAMPLER_STOP <event-id> <show-ns> [sample-id]`
- `SAMPLER_STATUS`

The provider-neutral public contract is `org.upp.audio.sampler-voice-engine/1`. These authenticated stdio commands are a local development adapter, not the interoperability standard.
