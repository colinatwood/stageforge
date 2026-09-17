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
- Current manager-integration implementation head before this continuity commit: `85e0b5f252b4bc9a3d81bccf8ff56eb2baf4699e`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection.

The CP86 portability-fix continuity head was fully green in all three required PR workflows. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because their authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 first added `NativeMidiInput`, with exact `sha256:` endpoint ownership, no name/index/default substitution, an 8192-byte callback SPSC ring, atomic drop accounting, explicit detach, and hosted-safe malformed/nonexistent-identity smoke coverage.

The ownership continuity head `7c27f84c...` is now fully green: Platform Modules run `35274677549`, Native Device Lifecycle `35274677696`, and StageForge CI `35274677632` all completed successfully. This verifies hosted build/fail-closed behavior only, not physical MIDI hardware.

The next implementation slice is now committed through `85e0b5f2...`:

- `MidiInputManager::attach()` extracts only the descriptor's exact `native=sha256:...` token and delegates target-OS ownership to `NativeMidiInput`;
- each target-OS device slot owns its native input independently, preserving the manager's multi-device model;
- `poll()` drains bounded callback bytes through the existing `MidiByteParser` and existing bounded `CapturedMidiInput` queue;
- native callback byte drops are folded into ingress drop audit accounting;
- rescans transfer ownership/parser/player state only when the exact hashed descriptor identity remains present; disappearance closes the old slot and therefore fails closed;
- Linux raw-MIDI behavior remains separate and unchanged in execution model.

The current manager-integration head has not yet produced PR workflow runs, so this slice is **implemented but not yet CI-verified**. Do not promote it to known-good until all required workflows complete successfully.

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

Inspect all PR #23 workflows for the manager-integration continuity successor of `85e0b5f252b4bc9a3d81bccf8ff56eb2baf4699e` and fix every compile/test failure before calling the slice green. Once green, add hosted-safe `MidiInputManager` coverage that proves malformed/nonexistent target identities fail closed, parser/queue injection remains bounded, rescans revoke disappeared identities, and audit counters remain coherent without requiring physical MIDI hardware. Then continue to the next repository-visible software backlog dependency. Do not infer physical hardware qualification from hosted CI.
