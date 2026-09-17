# StageForge Master Project File

> Canonical continuity record. Git is the source of truth; this file is the compact handoff when chat/session context disappears.

## Current baseline

- Repository: `colinatwood/stageforge`
- Canonical branch: `main`
- Active work: **Checkpoint 86 — full-engine target-OS audio streaming integration**
- Active branch: `checkpoint-86-backlog-reconcile-and-audio-stream`
- Active PR: **#21 — Checkpoint 86: integrate full-engine target-OS audio streaming**
- Safety branch before status mutation: `checkpoint-86-status-safety-5e81eb92`
- Safety branch before Linux portability fix: `checkpoint-86-linux-status-safety-9234a7d8`
- Engine integration commit: `fc1bf23d6370391225675cd2ae715c242b9e8090`
- Last fully green pre-status head: `5e81eb92f57d4ed7de22b75fa5f7c2c602e57326`
- Full-engine native status mutation: `3cc5a8c1db0d4d3816bc2734b195e9a38ed8f353`
- CI restored read-only: `b8226b7d279697ea6ca9d1d4b7c1f7365ff13872`
- Temporary status patcher removed: `aa57793e383b6c396d505e5f39f9ad5a089abcea`
- Hosted-safe full-engine status smoke extended: `1b3bef985c1a5e1ef232d22411b9305eed7b80c2`
- Linux status declaration portability fix: `b28152a5d7f1005c0c375e9d579e3cdee953102a`
- Verified CP86 continuity head before reconciliation: `c3a956ccfa9b76f162a96f4c307d5e7c9c7285fc`

## Checkpoint 86 implementation

The branch contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, and fail-closed unsupported conversion behavior.

`native/src/engine_main.cpp` consumes native playback/capture status on Windows/macOS. Commit `3cc5a8c1db0d4d3816bc2734b195e9a38ed8f353` wires `AUDIO_INPUT_STATUS`, `AUDIO_STREAM_STATUS`, and global `STATUS` to typed `EndpointStreamStats` projection. Native discontinuities are reported separately, native `xruns=0`, native render callbacks count as stream activity for rate measurement, and ALSA write timing remains zero for native execution.

Commit `1b3bef985c1a5e1ef232d22411b9305eed7b80c2` extends `ci/native_engine_stdio_smoke.py` on Windows/macOS to require global native discontinuity counters, require input/output status to expose separate `discontinuities` and `xruns`, and exercise fail-closed invalid audio activation without claiming or arming hardware.

The cleaned head `9234a7d8...` exposed one Linux-only compile defect: the non-target-OS status fallback instantiated the platform-neutral `EngineNativeAudioStatus` value while its declaration header was included only on Windows/macOS. StageForge CI run `35250234182` failed in Linux at those declarations; Windows and macOS engine builds/smokes succeeded. Platform Modules `35250234177` and Native Device Lifecycle `35250234279` succeeded. Commit `b28152a5...` makes the status declaration available to the Linux engine translation unit without linking or enabling native execution symbols; ALSA behavior and target-OS runtime fencing are unchanged.

## Verification state

- Pre-status integration head `5e81eb92...` was fully green: StageForge CI `35237441286`, Native Device Lifecycle `35237441287`, Platform Modules `35237441283`.
- Status-apply run `35243997245`: mutation job success; Windows x64 success; macOS Apple Silicon success; its Linux failure was the temporary `contents: write` CI-contract violation.
- Cleaned head `9234a7d8...`: Platform Modules `35250234177` success; Native Device Lifecycle `35250234279` success; StageForge CI `35250234182` failed only in Linux compilation because `EngineNativeAudioStatus` was not declared there. Windows/macOS jobs succeeded.
- Portability-fix continuity head `c3a956cc...` is fully green in all three required PR workflows. StageForge CI `35256713409` succeeded; Native Device Lifecycle `35256713592` succeeded; the same head has exactly three completed required workflow runs and all concluded success. This closes the CP86 hosted/software verification gate.

## Remaining Checkpoint 86 scope

- Reconcile AUD-035/AUD-036/DEV-033/DEV-034 against the authoritative backlog acceptance criteria before marking rows Done. Those row definitions are not stored in the repository text currently available through Git, so no row is closed merely from inference.
- Preserve qualification boundaries: CP86 hosted evidence verifies software/build/command behavior only, not physical hardware, licensed plugins, deployment, packages, or live external-environment qualification.

## Following wave

After CP86 backlog reconciliation, continue directly into target-OS MIDI attach/poll/event I/O. Target-OS MIDI enumeration and hash-only identity already exist, but `MidiInputManager::attach()` and `poll()` remain Linux-only execution paths: Windows/macOS currently enumerate descriptors yet fail closed on attach and perform no native event polling. This is the highest-leverage concrete software gap visible from repository state. Non-Linux `IsolatedPluginHost` verification-to-launch wiring remains another candidate and must be ordered by formal backlog acceptance criteria when those criteria are available.

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

Treat CP86 hosted/software verification as green. Obtain the authoritative acceptance definitions for AUD-035/AUD-036/DEV-033/DEV-034 from the backlog source before changing their status; do not infer Done from checkpoint labels alone. In parallel, begin the next unambiguous software implementation wave by adding target-OS MIDI input ownership and event ingestion behind `MidiInputManager`: exact selected hashed identity, explicit attach/detach, bounded queueing, Windows/macOS native callback/poll adaptation, fail-closed topology loss/revocation, hosted-safe smoke coverage, and no physical-hardware qualification claim.
