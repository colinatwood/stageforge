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
- Last fully green CP87 test head: `a926393236304c1f897ab7c1159e110ccd8b55fb`
- Current exact-identity/topology test head: `713c1959e1c112a64122d191d4b264aee2451f77`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 added `NativeMidiInput` with exact `sha256:` endpoint ownership, no name/index/default substitution, an 8192-byte callback SPSC ring, atomic drop accounting, explicit detach, and hosted-safe malformed/nonexistent-identity coverage. Target-OS ownership is wired behind `MidiInputManager::attach()`, independent per-device native ownership is retained across rescans only for the same exact identity, callback bytes drain through the existing parser/event queue, native ingress drops fold into audit accounting, and missing identities revoke ownership on rescan. Linux raw-MIDI execution remains separate.

The portability/API/parser repair chain is complete through `92d75d6b24bfa0e84cfff505e47887ee860dd449`, fully green in Platform Modules `35294440263`, Native Device Lifecycle `35294440265`, and StageForge CI `35294440235`. Manager identity/ingress/enumeration smokes through `a926393236304c1f897ab7c1159e110ccd8b55fb` are also fully green: StageForge CI `35305406823`, Native Device Lifecycle `35305406898`, and Platform Modules `35305406885`.

Commit `295befe88b2d635d97d0891d57b4a198fb0e0257` makes a target-OS rescan purge queued `CapturedMidiInput` records whose exact device identity is absent from the authoritative Windows/macOS snapshot. Commit `09ae96d2140d03505d72fdf67b1753152d4c6c3c` added deterministic hosted-safe revocation coverage. Its Platform Modules `35309213737`, Native Device Lifecycle `35309213729`, and Linux StageForge CI job are green, but Windows and macOS native tests failed. Inspection found the test's full framed SHA-256 identity could not even enter `inject()`: both `MidiDeviceDescriptor::id` and `CapturedMidiInput::device_id` were only 64 bytes while a target-OS framed `midi:<backend>:hash:sha256:<64 hex>` identity is longer than 64 bytes. That also exposed a production correctness defect: enumerated target-OS IDs were silently truncated, defeating exact selected identity lookup even though the native path retained the hash.

Commit `1f31808bf2f2ec988bb238c8c8beb071568bfbb2` expands descriptor/captured device identity storage to 128 bytes so complete framed SHA-256 identities survive end-to-end. Commit `381e318b0cf8a12d35504a7ba9977505de6bd883` makes hosted injection validate against the actual destination array sizes instead of the obsolete hard-coded 64-byte device limit. Commit `713c1959e1c112a64122d191d4b264aee2451f77` strengthens the target-OS smoke to require the exact prefix plus all 64 hash hex characters and exercises topology revocation with a complete backend-shaped identity. Fresh CI for this successor head is pending; do not call it green until workflows complete.

Next action: inspect/fix CI for `713c1959...`; once green, verify the complete software route `CapturedMidiInput -> MidiLearnRouter -> MidiMappedActionDispatcher -> ShowExecutionLoop` end-to-end with hosted-safe injection and no hardware claim. Reconcile AUD-035/AUD-036/DEV-033/DEV-034 only from authoritative acceptance definitions; do not infer Done from checkpoint labels.

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
