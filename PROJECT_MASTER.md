# StageForge Master Project File

> Canonical continuity record. Git is the source of truth; this file is the compact handoff when chat/session context disappears.

## Current baseline

- Repository: `colinatwood/stageforge`
- Canonical branch: `main`
- Active work: **Checkpoint 86 — full-engine target-OS audio streaming integration**
- Active branch: `checkpoint-86-backlog-reconcile-and-audio-stream`
- Active PR: **#21 — Checkpoint 86: integrate full-engine target-OS audio streaming**
- Safety branch before status mutation: `checkpoint-86-status-safety-5e81eb92`
- Engine integration commit: `fc1bf23d6370391225675cd2ae715c242b9e8090`
- Last fully green pre-status head: `5e81eb92f57d4ed7de22b75fa5f7c2c602e57326`
- Full-engine native status mutation: `3cc5a8c1db0d4d3816bc2734b195e9a38ed8f353`
- CI restored read-only: `b8226b7d279697ea6ca9d1d4b7c1f7365ff13872`
- Temporary status patcher removed: `aa57793e383b6c396d505e5f39f9ad5a089abcea`
- Hosted-safe full-engine status smoke extended: `1b3bef985c1a5e1ef232d22411b9305eed7b80c2`

## Checkpoint 86 implementation

The branch contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, and fail-closed unsupported conversion behavior.

`native/src/engine_main.cpp` now consumes native playback/capture status on Windows/macOS. Commit `3cc5a8c1db0d4d3816bc2734b195e9a38ed8f353` wires `AUDIO_INPUT_STATUS`, `AUDIO_STREAM_STATUS`, and global `STATUS` to typed `EndpointStreamStats` projection. Native discontinuities are reported separately, native `xruns=0`, native render callbacks count as stream activity for rate measurement, and ALSA write timing remains zero for native execution.

The temporary write-enabled CI job succeeded in producing that engine mutation. Its Linux release job failed only because the temporary workflow deliberately changed `permissions.contents` to `write`, violating the repository's CI-contract test requiring `contents: read`; Windows and macOS build/platform smoke jobs succeeded. The production workflow was restored byte-equivalent to the prior read-only form in `b8226b7d...`, and the temporary patcher was deleted in `aa57793e...`.

Commit `1b3bef985c1a5e1ef232d22411b9305eed7b80c2` extends `ci/native_engine_stdio_smoke.py` on Windows/macOS to require global native discontinuity counters, require input/output status to expose separate `discontinuities` and `xruns`, and exercise fail-closed invalid audio activation without claiming or arming hardware.

## Verification state

- Pre-status integration head `5e81eb92...` was fully green: StageForge CI `35237441286`, Native Device Lifecycle `35237441287`, Platform Modules `35237441283`.
- Status-apply run `35243997245`: mutation job success; Windows x64 success; macOS Apple Silicon success; Linux failure was the expected temporary `contents: write` CI-contract violation, not an engine compile/test failure.
- Final cleaned/smoke-extended head still requires all three required workflow conclusions before CP86 is called complete.

## Remaining Checkpoint 86 scope

- Require StageForge CI, Platform Modules, and Native Device Lifecycle green on the cleaned/smoke-extended head.
- Fix any target-OS command-smoke or compile failure.
- Reconcile AUD-035/AUD-036/DEV-033/DEV-034 against exact acceptance criteria before marking rows Done.

## Following wave

After CP86 verification/reconciliation, continue directly into the highest-leverage unresolved software dependency. Current evidence points to target-OS MIDI attach/poll/event I/O: target-OS MIDI enumeration/identity exists, while full-engine `MIDI_ATTACH`/`MIDI_INPUT_POLL` still depend on the recovered `MidiInputManager` execution path. Non-Linux `IsolatedPluginHost` verification-to-launch wiring remains another candidate and must be ordered by formal backlog acceptance criteria.

## Verification entry points

```bash
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

Linux developer-alpha software gate:

```bash
python scripts/release-check.py
```

## Qualification boundary

Hosted/software evidence does not by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, live Windows/macOS endpoint behavior, or audio quality. Hosted Windows may expose no usable endpoint. Capture packet discontinuity metadata is not currently consumed by the recovered engine capture callback. Native endpoint discontinuities are not ALSA xruns. `physicalOutputsArmed=false` remains unchanged.

## Continuity protocol

1. Read this file and inspect current branch/PR history before substantive work.
2. Create a safety/checkpoint branch before substantial mutations.
3. Commit each meaningful implementation/test/documentation checkpoint to GitHub.
4. Verify CI before calling a checkpoint known-good.
5. Update this file before ending or when context is crowded.
6. If chat conflicts with Git, Git wins.

## Exact next action

Observe all three required workflow runs for the cleaned head after `1b3bef985c1a5e1ef232d22411b9305eed7b80c2` (or this continuity commit). Fix any failure. Once green, reconcile AUD-035/AUD-036/DEV-033/DEV-034 against their exact acceptance criteria and close only rows actually satisfied by CP85/CP86 evidence. Then continue directly into target-OS MIDI attach/poll/event I/O if it remains an open software row.
