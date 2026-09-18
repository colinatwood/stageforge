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
- Last fully green CP87 manager/ingress continuity head: `731f3b2e3992fc958f816a862a6ea875241a2746`
- Current test head: `a926393236304c1f897ab7c1159e110ccd8b55fb`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 added `NativeMidiInput` with exact `sha256:` endpoint ownership, no name/index/default substitution, an 8192-byte callback SPSC ring, atomic drop accounting, explicit detach, and hosted-safe malformed/nonexistent-identity coverage. Target-OS ownership is wired behind `MidiInputManager::attach()`, independent per-device native ownership is retained across rescans only for the same exact identity, callback bytes drain through the existing parser/event queue, native ingress drops fold into audit accounting, and missing identities revoke ownership on rescan. Linux raw-MIDI execution remains separate.

The portability/API/parser repair chain is complete through `92d75d6b24bfa0e84cfff505e47887ee860dd449`, which is fully green in Platform Modules `35294440263`, Native Device Lifecycle `35294440265`, and StageForge CI `35294440235`. This includes the incomplete-type-safe native owner boundary, correct `DeviceRecord::native_hash`/monitor `snapshot()` usage, and MIDI realtime filtering that preserves running status.

Commit `b4487b00d55205bfa16410e969df8380f9b5c5cb` added a hosted-safe `MidiInputManager` identity smoke; Platform Modules `35297780891`, Native Device Lifecycle `35297781074`, and StageForge CI `35297780879` are green.

Commit `cdab498323c1a2fabd8c93220015daceed9a680a` extended the smoke across the software ingress boundary: deterministic injected Note On data emerges as the same `CapturedMidiInput` with exact device/player identity and timestamp/data, queue drain semantics and audit counters are checked, and physical outputs remain unarmed. Continuity head `731f3b2e3992fc958f816a862a6ea875241a2746` is fully green: StageForge CI `35301603223`, Platform Modules `35301603219`, and Native Device Lifecycle `35301603220` all completed successfully.

This run compared the active branch with the prior continuity head and found no external advancement, then made concrete test progress. A provisional private topology-fence declaration commit `cac7a54d...` was immediately neutralized by `9fe8ad9...` before implementation because landing a declaration-only seam would create an unsafe intermediate build. Commit `a926393236304c1f897ab7c1159e110ccd8b55fb` then added hosted-safe target-OS enumeration assertions: any enumerated Windows/macOS MIDI endpoint must expose only the backend plus `sha256:` hash identity, never name/index identity, while the test remains vacuously safe on runners with no MIDI endpoints and never opens hardware. Fresh workflows are queued: StageForge CI `35305406823`, Native Device Lifecycle `35305406898`, Platform Modules `35305406885`.

Next action: inspect/fix CI for `a9263932...`. Then implement deterministic topology-loss fencing as a complete code+test slice, preferably by extracting reconciliation/purge logic that can be exercised without physical hardware; stale queued target-OS events for a disappeared exact identity must not reach mapped-action dispatch. After that, verify `CapturedMidiInput -> MidiLearnRouter -> MidiMappedActionDispatcher -> ShowExecutionLoop` end-to-end. Do not infer physical MIDI qualification from hosted execution.

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
