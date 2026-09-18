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
- Last fully green CP87 implementation/test head: `3246d63eaeb5fcba50af6932eeed5277a290c81a`
- Current implementation/test head: `0ad396841d0d015be2841b82b24f06b6dd965878`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 now contains exact hash-only WinMM/CoreMIDI ownership behind `MidiInputManager`, explicit attach/detach, an 8192-byte callback SPSC ring and per-device poll bound, drop accounting with parser reset, exact device/player ownership epochs, topology/rescan and asynchronous callback revocation, queued-event purging at detach/revocation boundaries, and the hosted-safe `CapturedMidiInput -> MidiLearnRouter -> MidiMappedActionDispatcher -> ShowExecutionLoop` path. Linux raw-MIDI execution remains separate and unchanged by target-OS branches.

Key verified checkpoints include: end-to-end mapping `15cecff1c919b8d0e2e3a3c7b409b63e490b9be8`; bounded ingestion `b4a40fc8816b32aed7e1cf87ca6fe69697d88ff0`; overflow/parser fencing `81ec3033c5ce8abc6c44576ae09beeba355ab23d`; WinMM revocation `26f8cd0dadda36568765a3c41a967cd3b6d1ce3d`; CoreMIDI removal revocation `df5b486c9672f965ed74cadc86e6ecb0c357dbdf`; mid-poll revocation fencing `d2c56d3f89a953544e9ea53ac96c6a4d368ddf08`; exact device/player ownership `79eb081ee9a67f282d84366282faac7fd1af6c1a`; explicit detach queue fencing `a48cf4572602197799dbee82a8f07bdde409d72d`; and asynchronous revocation queue fencing `0c93b79bc7df228fdacb754ec989508625e2fbf3`.

Commit `b8b880794b004370da59e364e45ae135816d6145` tightened `NativeMidiInput::attach()` to canonical lowercase SHA-256 tokens. Commit `94c3d1584301dad132cdf1a10e240650bab4f0cf` added malformed-token coverage and exposed a C++ language-level portability regression. Commit `3246d63eaeb5fcba50af6932eeed5277a290c81a` repaired it without changing validation semantics and is fully green: Platform Modules `35394828365`, Native Device Lifecycle `35394828378`, StageForge CI `35394828359`.

Commit `28ef56cd05040fcaa2e772873fd0dd60f8ab28e7` adds a pure exact-framing decoder for manager-owned target-OS identities. Commit `805717acfe299881f2ce326ae255da9e53a662d2` wires `MidiInputManager::attach()` through that decoder, so a descriptor path must be exactly `<backend>:hash:sha256:<64 lowercase hex>` for the expected platform backend rather than merely containing a `:hash:` substring. Commit `0ad396841d0d015be2841b82b24f06b6dd965878` adds deterministic hosted coverage for valid WinMM/CoreMIDI framing, backend mismatch, prefixed/injected framing, name-bearing framing, and uppercase digest rejection. Fresh CI had not appeared at immediate inspection.

Next action: inspect/fix CI for `0ad39684...`; if green, inspect the remaining CP87 software-only ingress surface and add the smallest safe meaningful checkpoint. In particular, do not claim physical MIDI qualification from hosted runners. Reconcile AUD-035/AUD-036/DEV-033/DEV-034 only from authoritative acceptance definitions; do not infer Done from checkpoint labels.

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
