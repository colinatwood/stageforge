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
- Last fully green CP87 implementation/test head: `454425a9dba2b57a296fbb1d55fb247fe88a6526`
- Current implementation/test head: `d2c56d3f89a953544e9ea53ac96c6a4d368ddf08`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 added `NativeMidiInput` with exact `sha256:` endpoint ownership, no name/index/default substitution, an 8192-byte callback SPSC ring, atomic drop accounting, explicit detach, and hosted-safe malformed/nonexistent-identity coverage. Target-OS ownership is wired behind `MidiInputManager::attach()`, independent per-device native ownership is retained across rescans only for the same exact identity, callback bytes drain through the existing parser/event queue, native ingress drops fold into audit accounting, and missing identities revoke ownership on rescan. Linux raw-MIDI execution remains separate.

The portability/API/parser repair chain is complete through `92d75d6b24bfa0e84cfff505e47887ee860dd449`, fully green in Platform Modules `35294440263`, Native Device Lifecycle `35294440265`, and StageForge CI `35294440235`. Manager identity/ingress/enumeration smokes through `a926393236304c1f897ab7c1159e110ccd8b55fb` are also fully green: StageForge CI `35305406823`, Native Device Lifecycle `35305406898`, and Platform Modules `35305406885`.

Commit `295befe88b2d635d97d0891d57b4a198fb0e0257` makes a target-OS rescan purge queued `CapturedMidiInput` records whose exact device identity is absent from the authoritative Windows/macOS snapshot. Commit `09ae96d2140d03505d72fdf67b1753152d4c6c3c` added deterministic hosted-safe revocation coverage. Its Platform Modules `35309213737`, Native Device Lifecycle `35309213729`, and Linux StageForge CI job are green, but Windows and macOS native tests exposed that 64-byte descriptor/captured identity storage truncated the complete `midi:<backend>:hash:sha256:<64 hex>` identity.

Commit `1f31808bf2f2ec988bb238c8c8beb071568bfbb2` expands descriptor/captured device identity storage to 128 bytes. Commit `381e318b0cf8a12d35504a7ba9977505de6bd883` makes hosted injection validate against actual destination sizes. Commit `713c1959e1c112a64122d191d4b264aee2451f77` requires the exact prefix plus all 64 hash hex characters and exercises topology revocation with a complete backend-shaped identity. CI for `713c1959...` exposed a Windows stack hazard from a second queue-capacity `CapturedMidiInput` array in `scan()`.

Commit `5192e0aacf37a53afef3741be2656004a6dc1907` removes that second queue-capacity stack allocation. Target-OS topology revocation filters the existing bounded ring in place over exactly the pre-scan queue count, preserving surviving events without heap allocation or queue reordering and leaving Linux behavior unchanged. Continuity head `466686076402edd6a77c7f804d7dc3f949964b19` is fully green: Platform Modules `35317755632`, Native Device Lifecycle `35317755604`, and StageForge CI `35317755653`.

Commit `15cecff1c919b8d0e2e3a3c7b409b63e490b9be8` adds a hosted-safe end-to-end software smoke wired into CTest. It injects a `CapturedMidiInput` through `MidiInputManager`, resolves the stable device token used by the engine, matches it in `MidiLearnRouter`, converts through `MidiMappedActionDispatcher`, submits to `ShowExecutionLoop`, drains the due event, and verifies authoritative automation payload plus fail-closed physical-output status. Continuity head `464a99c8ff2d35b0d62dc844a46aed5f16717365` is fully green: Platform Modules `35322139702`, Native Device Lifecycle `35322139630`, and StageForge CI `35322139628`.

Commit `b4a40fc8816b32aed7e1cf87ca6fe69697d88ff0` bounds Windows/macOS native ingestion to 8192 bytes per attached device per `MidiInputManager::poll()` call. Commit `9b5d0a969e9a261a2df2e4f4bad648a784307798` tightens hosted-safe ownership coverage to the complete framed `midi:<backend>:hash:sha256:<64 hex>` identity. Continuity head `856459676c5f5d0a2a1419dfb06ac5cc7f1de4e5` is fully green: Platform Modules `35327272599`, Native Device Lifecycle `35327272575`, and StageForge CI `35327272661`.

Commit `686171cb5d0f4f4cdc53a3ea199b5507c025d918` resets `NativeMidiInput` callback-ring drop accounting at every valid attach attempt, alongside ring cursors, so overflow telemetry cannot leak across exact-identity ownership epochs. It is fully green: Native Device Lifecycle `35332512557`, StageForge CI `35332512577`, and Platform Modules `35332512574`.

Commit `81ec3033c5ce8abc6c44576ae09beeba355ab23d` adds fail-closed parser handling for target-OS native ring overflow. `MidiInputManager::poll()` samples drop accounting after each bounded native drain chunk; if any byte was lost since the previous sample it accounts the loss, resets parser/running-status state, and discards the rest of that poll's native bytes for the affected device rather than allowing an overflow-corrupted byte stream to synthesize a MIDI message. A final drop sample resets parser state for loss racing the end of the bounded drain. Linux behavior is unchanged. It is fully green: Native Device Lifecycle `35337693147`, Platform Modules `35337692951`, and StageForge CI `35337692906`.

Commit `d64acca679e625e0f02965026e6f731b26577177` adds deterministic hosted-safe parser-boundary coverage to `midi_manager_hosted_smoke`: a partial Note On is reset at the same parser seam used by overflow handling, trailing data bytes are proven unable to complete a synthetic message, and a subsequent complete status/data message still parses normally. This deliberately avoids adding a production identity-bypass hook merely for tests. It is fully green: Platform Modules `35342520810`, Native Device Lifecycle `35342520817`, and StageForge CI `35342520857`.

Commit `26f8cd0dadda36568765a3c41a967cd3b6d1ce3d` adds an immediate WinMM callback-side revocation fence. `MIM_CLOSE`, `MIM_ERROR`, or `MIM_LONGERROR` atomically revoke the attachment; subsequent short-message callbacks are ignored, `attached()` reports false, and `poll_bytes()` refuses to drain stale queued bytes. The next `MidiInputManager::poll()` therefore closes the slot before parser/event dispatch. A new valid attach epoch clears the revocation flag. This implementation head is fully green: Platform Modules `35348050975`, Native Device Lifecycle `35348050977`, and StageForge CI `35348051004`.

Commit `df5b486c9672f965ed74cadc86e6ecb0c357dbdf` adds the corresponding CoreMIDI notification fence. The MIDI client now receives topology notifications; removal of the exact selected source atomically revokes the attachment, subsequent packet callbacks are ignored, `attached()` fails closed, and `poll_bytes()` cannot release stale queued bytes. The selected `MIDIEndpointRef` is mirrored into an atomic integer solely for notification-thread identity comparison, while control-thread detach clears it before disposing CoreMIDI ownership. Linux and WinMM behavior are unchanged. This implementation head is fully green: Platform Modules `35349322466`, Native Device Lifecycle `35349322471`, and StageForge CI `35349322591`.

Commit `454425a9dba2b57a296fbb1d55fb247fe88a6526` strengthens the target-OS `NativeMidiInput` hosted smoke around the revocation/cleanup contract without adding a production identity-bypass seam: null/zero-capacity polling fails closed, malformed and nonexistent exact hashes cannot acquire or release bytes, and repeated detach remains safe/idempotent for manager cleanup after asynchronous topology loss. It is fully green: Platform Modules `35353632131`, Native Device Lifecycle `35353632062`, and StageForge CI `35353632053`.

Commit `d2c56d3f89a953544e9ea53ac96c6a4d368ddf08` closes a mid-poll asynchronous revocation race in the target-OS manager path. After every native `poll_bytes()` drain attempt, `MidiInputManager::poll()` rechecks native attachment before parsing the returned chunk. If WinMM/CoreMIDI revokes ownership during that drain, the slot is closed and those bytes are discarded rather than becoming `CapturedMidiInput`; the post-loop drop sample is skipped after closure. Linux behavior is unchanged. Fresh CI is pending.

Next action: inspect/fix CI for `d2c56d3f...`; if green, inspect remaining CP87 software-only gaps and close any deterministic hosted-safe lifecycle coverage still missing. Reconcile AUD-035/AUD-036/DEV-033/DEV-034 only from authoritative acceptance definitions; do not infer Done from checkpoint labels.

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
