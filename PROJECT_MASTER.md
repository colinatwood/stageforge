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
- Current manager-integration fix head: `37165450d8832382c69851833c31612adf930a37`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection.

The CP86 portability-fix continuity head was fully green in all three required PR workflows. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because their authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 first added `NativeMidiInput`, with exact `sha256:` endpoint ownership, no name/index/default substitution, an 8192-byte callback SPSC ring, atomic drop accounting, explicit detach, and hosted-safe malformed/nonexistent-identity smoke coverage.

The ownership continuity head `7c27f84c...` is fully green: Platform Modules run `35274677549`, Native Device Lifecycle `35274677696`, and StageForge CI `35274677632` all completed successfully. This verifies hosted build/fail-closed behavior only, not physical MIDI hardware.

Manager integration through `cfef6391...` adds exact-hash target-OS ownership behind `MidiInputManager::attach()`, independent per-device native ownership, bounded callback-byte draining through the existing parser/event queue, ingress-drop audit folding, and exact-identity topology-loss fencing on rescan. Linux raw-MIDI execution remains separate.

PR workflows for `cfef6391...` completed with Platform Modules `35279980955` green and Native Device Lifecycle `35279980889` green. StageForge CI `35279980899` had Linux and Windows green but failed its macOS Apple Silicon build because libc++ instantiated `std::unique_ptr<NativeMidiInput>` destruction while the type was incomplete.

The first attempted portability fix `924f43c7...` referenced nonexistent `stageforge/native_midi_input.hpp` and is superseded. Commits `85d70047...` and `bd67c126...` replaced that approach with an incomplete-type-safe custom deleter.

Fresh CI for continuity head `318910586b4f220111009b7b497e1fa27b782d63` proved that custom-deleter boundary itself compiles far enough to expose the next concrete manager errors. Platform Modules run `35287146757` and Native Device Lifecycle `35287146713` are green. StageForge CI `35287146739` failed Windows/macOS native-engine compilation because `midi_input.cpp` incorrectly referenced nonexistent `DeviceRecord::identity_hash` and `DeviceMonitor::scan()`; the actual APIs are `DeviceRecord::native_hash` and active-monitor `snapshot()`.

Commit `d3f695fcd529fa7fe7713d411b350ab71f290215` fixed those API mismatches. Fresh PR CI on continuity head `fa4fa4c5decfb71e3340f55d98e52ba819012547` then built the native engine successfully on Windows and macOS, but StageForge CI run `35293794213` failed `stageforge_native_tests` on both targets at `test_midi_byte_parser`: realtime byte `0xF8` was emitted as a mapped MIDI event even though the existing parser contract requires realtime bytes to leave an in-progress channel message untouched and not enter the mapped-action path. Platform Modules `35293794250` and Native Device Lifecycle `35293794204` remained green. Linux's release gate failed in the same StageForge CI run and must be rechecked after the parser correction.

Commit `37165450d8832382c69851833c31612adf930a37` restores that parser contract by filtering MIDI realtime bytes before message-state handling, preserving running status and the partially received channel message. This is a software-only correction; fresh PR CI is required before the manager-integration slice is called green.

Next action: inspect fresh CI for `37165450...`; fix any remaining release/native-test failure. Once green, add hosted-safe manager-level tests for exact-hash attach rejection/topology revocation and verify the existing `CapturedMidiInput -> MidiLearnRouter -> MidiMappedActionDispatcher -> ShowExecutionLoop` path without claiming physical MIDI qualification.

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
