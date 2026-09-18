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
- Last fully green CP87 implementation/test head: `a48cf4572602197799dbee82a8f07bdde409d72d`
- Current implementation head: `96e0a46bd7f889b57689bacfce69a843a0127d68`

## Checkpoint 86 verified state

CP86 contains target-OS native audio ownership, strict hash-only identity decoding, four independent playback/capture slots, full-engine linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, same-owner-thread service, exact selected identity fencing, explicit rearm, no default endpoint substitution, fail-closed unsupported conversion behavior, and typed native status projection. AUD-035/AUD-036/DEV-033/DEV-034 remain unclosed because authoritative acceptance definitions are not stored in repository text available through Git.

## Checkpoint 87 implementation

CP87 added `NativeMidiInput` with exact `sha256:` endpoint ownership, no name/index/default substitution, an 8192-byte callback SPSC ring, atomic drop accounting, explicit detach, and hosted-safe malformed/nonexistent-identity coverage. Target-OS ownership is wired behind `MidiInputManager::attach()`, independent per-device native ownership is retained across rescans only for the same exact identity, callback bytes drain through the existing parser/event queue, native ingress drops fold into audit accounting, and missing identities revoke ownership on rescan. Linux raw-MIDI execution remains separate.

The portability/API/parser repair chain is complete through `92d75d6b24bfa0e84cfff505e47887ee860dd449`, fully green in Platform Modules `35294440263`, Native Device Lifecycle `35294440265`, and StageForge CI `35294440235`. Manager identity/ingress/enumeration smokes through `a926393236304c1f897ab7c1159e110ccd8b55fb` are also fully green: StageForge CI `35305406823`, Native Device Lifecycle `35305406898`, and Platform Modules `35305406885`.

Commit `295befe88b2d635d97d0891d57b4a198fb0e0257` makes a target-OS rescan purge queued `CapturedMidiInput` records whose exact device identity is absent from the authoritative Windows/macOS snapshot. Commit `09ae96d2140d03505d72fdf67b1753152d4c6c3c` added deterministic hosted-safe revocation coverage. Its Platform Modules `35309213737`, Native Device Lifecycle `35309213729`, and Linux StageForge CI job are green, but Windows and macOS native tests exposed that 64-byte descriptor/captured identity storage truncated the complete target-OS identity.

Commit `1f31808bf2f2ec988bb238c8c8beb071568bfbb2` expands descriptor/captured device identity storage to 128 bytes. Commit `381e318b0cf8a12d35504a7ba9977505de6bd883` makes hosted injection validate against actual destination sizes. Commit `713c1959e1c112a64122d191d4b264aee2451f77` requires the exact prefix plus all 64 hash hex characters and exercises topology revocation with a complete backend-shaped identity.

Commit `5192e0aacf37a53afef3741be2656004a6dc1907` removes the Windows stack hazard from topology queue filtering. Continuity head `466686076402edd6a77c7f804d7dc3f949964b19` is fully green: Platform Modules `35317755632`, Native Device Lifecycle `35317755604`, and StageForge CI `35317755653`.

Commit `15cecff1c919b8d0e2e3a3c7b409b63e490b9be8` adds the hosted-safe end-to-end `CapturedMidiInput -> MidiLearnRouter -> MidiMappedActionDispatcher -> ShowExecutionLoop` smoke. Continuity head `464a99c8ff2d35b0d62dc844a46aed5f16717365` is fully green: Platform Modules `35322139702`, Native Device Lifecycle `35322139630`, and StageForge CI `35322139628`.

Commit `b4a40fc8816b32aed7e1cf87ca6fe69697d88ff0` bounds Windows/macOS native ingestion to 8192 bytes per attached device per manager poll. Commit `9b5d0a969e9a261a2df2e4f4bad648a784307798` tightens hosted ownership coverage to the complete framed identity. Continuity head `856459676c5f5d0a2a1419dfb06ac5cc7f1de4e5` is fully green: Platform Modules `35327272599`, Native Device Lifecycle `35327272575`, and StageForge CI `35327272661`.

Commit `686171cb5d0f4f4cdc53a3ea199b5507c025d918` resets callback-ring drop accounting at each valid attachment epoch. It is fully green: Native Device Lifecycle `35332512557`, StageForge CI `35332512577`, and Platform Modules `35332512574`.

Commit `81ec3033c5ce8abc6c44576ae09beeba355ab23d` adds fail-closed parser handling for native-ring overflow. It is fully green: Native Device Lifecycle `35337693147`, Platform Modules `35337692951`, and StageForge CI `35337692906`. Commit `d64acca679e625e0f02965026e6f731b26577177` adds deterministic parser-boundary coverage and is fully green: Platform Modules `35342520810`, Native Device Lifecycle `35342520817`, and StageForge CI `35342520857`.

Commit `26f8cd0dadda36568765a3c41a967cd3b6d1ce3d` adds WinMM callback-side revocation and is fully green: Platform Modules `35348050975`, Native Device Lifecycle `35348050977`, and StageForge CI `35348051004`. Commit `df5b486c9672f965ed74cadc86e6ecb0c357dbdf` adds the CoreMIDI source-removal notification fence and is fully green: Platform Modules `35349322466`, Native Device Lifecycle `35349322471`, and StageForge CI `35349322591`.

Commit `454425a9dba2b57a296fbb1d55fb247fe88a6526` strengthens hosted target-OS lifecycle coverage and is fully green: Platform Modules `35353632131`, Native Device Lifecycle `35353632062`, and StageForge CI `35353632053`. Commit `d2c56d3f89a953544e9ea53ac96c6a4d368ddf08` closes the mid-poll asynchronous revocation race and is fully green: Platform Modules `35359922660`, Native Device Lifecycle `35359922665`, and StageForge CI `35359922717`.

Commit `79eb081ee9a67f282d84366282faac7fd1af6c1a` tightens ownership to the exact device/player pair and is fully green: Platform Modules `35364791145`, Native Device Lifecycle `35364791252`, and StageForge CI `35364791133`. Commits `1b805d507d58472ea707f22054757cfbfe041b23` and `c50390e6e0e5a3d4d9ad2e164a25e1fb42a13e57` factor the production reuse decision into `midi_attachment_owner_matches()`. Commit `401aabb81d7398e55fe25f6f3323489b3dc3b6f5` adds hosted-safe same-owner/cross-owner coverage and is fully green: Platform Modules `35365922617`, Native Device Lifecycle `35365922401`, and StageForge CI `35365922441`.

Commit `a48cf4572602197799dbee82a8f07bdde409d72d` makes explicit Windows/macOS `MidiInputManager::detach()` an ownership-epoch boundary for the captured-event queue. It is fully green: Platform Modules `35371820916`, Native Device Lifecycle `35371820935`, and StageForge CI `35371820943`.

Commits `f18fbf291465cd8c000dd81e6e871c4cd5e8bea3` and `e3772a88595b7f2856bccbb066add792501012ac` factor the detach queue decision into the pure `midi_event_survives_detach()` predicate and wire production target-OS filtering through it. Commit `96e0a46bd7f889b57689bacfce69a843a0127d68` adds hosted-safe coverage proving the detached exact identity is rejected while unrelated device events survive, without adding a native device-opening bypass seam. Fresh workflows are queued: Native Device Lifecycle `35377736501`, StageForge CI `35377736513`, and Platform Modules `35377736529`.

Next action: inspect/fix CI for `96e0a46b...`; if green, inspect CP87 for any remaining software-only identity/revocation/ingress gap and close the smallest safe slice. Reconcile AUD-035/AUD-036/DEV-033/DEV-034 only from authoritative acceptance definitions; do not infer Done from checkpoint labels.

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
