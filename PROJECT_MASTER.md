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
- CP87 module/build head before continuity update: `92ad606dd03633baadb836f903677e793c298355`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection.

The portability-fix continuity head `c3a956ccfa9b76f162a96f4c307d5e7c9c7285fc` was fully green in all three required PR workflows: StageForge CI `35256713409`, Native Device Lifecycle `35256713592`, and Platform Modules. This closes the CP86 hosted/software verification gate. Commit `b1a51258...` records that result and identifies target-OS MIDI ingress as the next unambiguous software gap.

AUD-035/AUD-036/DEV-033/DEV-034 are not marked Done because their authoritative acceptance definitions are not stored in repository text available through Git. Do not infer acceptance from checkpoint labels.

## Checkpoint 87 implementation

The pre-CP87 `MidiInputManager` enumerates hash-only Windows/CoreMIDI descriptors, but its `attach()` and `poll()` execution paths are Linux-only. CP87 begins by adding `NativeMidiInput`, a target-OS ownership module with these boundaries:

- attach only by the exact `sha256:` native identity emitted by the existing monitor model; no name/index/default endpoint substitution;
- Windows opens only WinMM inputs whose device-interface-backed native hash can be reconstructed exactly; volatile index/name fallback identities remain deliberately unattachable;
- macOS resolves the exact CoreMIDI source native hash and connects an owned input port;
- OS callbacks append bytes to a fixed 8192-byte SPSC ring with an atomic drop counter; callback ingress does not allocate;
- explicit detach stops/disconnects and disposes the owned OS handle/port;
- hosted-safe smoke uses malformed/nonexistent hashes only and therefore does not claim physical MIDI qualification.

Commits on the CP87 branch:

- `d7944204...` — target-OS bounded MIDI ownership interface.
- `2dc47d0f...` — Windows/CoreMIDI exact-hash ownership and callback byte ingress.
- `747f0397...` — hosted-safe fail-closed ownership smoke.
- `92ad606d...` — build/test integration into `stageforge_devices`.

PR #23 was opened against the CP86 continuity branch to trigger the target-OS workflows. At the time this continuity record was written, workflow runs had not yet appeared for `92ad606d...`; therefore CP87 is implemented but **not yet CI-verified**.

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

Hosted/software evidence does not by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, live Windows/macOS endpoint behavior, or audio quality. CP87's current smoke verifies fail-closed ownership behavior without opening a real endpoint. `physicalOutputsArmed=false` remains unchanged.

## Continuity protocol

1. Read this file and inspect current branch/PR history before substantive work.
2. Create a safety/checkpoint branch before substantial mutations.
3. Commit each meaningful implementation/test/documentation checkpoint to GitHub.
4. Verify CI before calling a checkpoint known-good.
5. Update this file before ending or when context is crowded.
6. If chat conflicts with Git, Git wins.

## Exact next action

Inspect all PR #23 workflows for `92ad606dd03633baadb836f903677e793c298355` (or this continuity successor) and fix any Windows/macOS compile or smoke failure. Once the ownership module is green, integrate it behind `MidiInputManager::attach()`, `detach()`, and `poll()` using the descriptor's exact `native=` hash token, feed drained native bytes through the existing `MidiByteParser`, preserve bounded `CapturedMidiInput` queueing/audit counters, and fail closed when a rescan no longer contains the exact attached identity. Add hosted-safe manager command/smoke coverage. Do not claim physical MIDI hardware qualification from hosted CI.
