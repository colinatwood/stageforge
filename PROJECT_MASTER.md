# StageForge Master Project File

> Canonical continuity record. Git is the source of truth; this file is the compact handoff when chat/session context disappears.

## Current baseline

- Repository: `colinatwood/stageforge`
- Canonical branch: `main`
- Completed hosted/software gate: **Checkpoint 86 — full-engine target-OS audio streaming integration**
- CP86 continuity head: `b1a51258b7752eb08a4711dec60b9941d0f79a98`
- Active work: **Checkpoint 87 — target-OS MIDI input ownership and event ingestion**
- Active branch: `checkpoint-87-native-midi-input`
- Active PR: **#23 — Checkpoint 87: add target-OS MIDI input ownership**
- Last fully green CP87 ownership head: `7c27f84c85b37cfb807e68d8678acaf02f58593c`
- Manager-integration continuity head: `cfef6391ad5ffba44c6eef328399efe45f1559bc`
- Current portability-fix implementation head: `924f43c7a6c4b7ae60338285f8fad009907dbddf`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection.

The CP86 portability-fix continuity head was fully green in all three required PR workflows. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because their authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 first added `NativeMidiInput`, with exact `sha256:` endpoint ownership, no name/index/default substitution, an 8192-byte callback SPSC ring, atomic drop accounting, explicit detach, and hosted-safe malformed/nonexistent-identity smoke coverage.

The ownership continuity head `7c27f84c...` is fully green: Platform Modules run `35274677549`, Native Device Lifecycle `35274677696`, and StageForge CI `35274677632` all completed successfully. This verifies hosted build/fail-closed behavior only, not physical MIDI hardware.

Manager integration through `cfef6391...` adds exact-hash target-OS ownership behind `MidiInputManager::attach()`, independent per-device native ownership, bounded callback-byte draining through the existing parser/event queue, ingress-drop audit folding, and exact-identity topology-loss fencing on rescan. Linux raw-MIDI execution remains separate.

PR workflows for `cfef6391...` completed with Platform Modules `35279980955` green and Native Device Lifecycle `35279980889` green. StageForge CI `35279980899` had Linux and Windows green but failed its macOS Apple Silicon build. The failure was compile-time only: libc++ instantiated `std::unique_ptr<NativeMidiInput>` destruction from `DeviceSlot` while `NativeMidiInput` was only forward-declared in `midi_input.hpp` (`invalid application of sizeof to an incomplete type`).

Commit `924f43c7...` fixes that portability defect by including `stageforge/native_midi_input.hpp` in `midi_input.hpp` on Windows/macOS, making the owned type complete where `DeviceSlot` destruction is instantiated. This does not change runtime identity, attachment, queueing, or physical-output behavior. Fresh PR CI for this fix is pending; do not call the manager-integration slice green until all required workflows succeed.

## Verification entry points

```bash
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
python scripts/release-check.py
```

## Qualification boundary

Hosted/software evidence does not by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, live Windows/macOS endpoint behavior, or audio quality. CP87 smokes may verify fail-closed behavior without opening a real endpoint. `physicalOutputsArmed=false` remains unchanged.

## Continuity protocol

1. Read this file and inspect current branch/PR history before substantive work.
2. Create a safety/checkpoint branch before substantial mutations.
3. Commit each meaningful implementation/test/documentation checkpoint to GitHub.
4. Verify CI before calling a checkpoint known-good.
5. Update this file before ending or when context is crowded.
6. If chat conflicts with Git, Git wins.

## Exact next action

Inspect all PR #23 workflows for portability-fix head `924f43c7a6c4b7ae60338285f8fad009907dbddf` and fix every compile/test failure before calling manager integration green. Once green, add hosted-safe `MidiInputManager` coverage proving malformed/nonexistent target identities fail closed, parser/queue injection remains bounded, rescans revoke disappeared identities, and audit counters remain coherent without requiring physical MIDI hardware. Then continue to the next repository-visible software backlog dependency. Do not infer physical hardware qualification from hosted CI.
