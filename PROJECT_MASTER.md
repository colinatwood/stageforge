# StageForge Master Project File

> Canonical continuity record for development sessions. Git remains the source of truth; this file is the compact handoff point when chat/session context runs out.

## Current baseline

- Repository: `colinatwood/stageforge`
- Canonical branch: `main`
- Last known-good main commit: `84f6da331a363a4638a7d17052796cbc3f861cf0`
- Latest completed milestone: **Checkpoint 85 — bridge native target-OS devices into full engine**
- Active work: **Checkpoint 86 — full-engine target-OS audio streaming integration**
- Active branch: `checkpoint-86-backlog-reconcile-and-audio-stream`
- Active PR: **#21 — Checkpoint 86: integrate full-engine target-OS audio streaming**
- Latest verified Checkpoint 86 branch commit: `8714e824790b35d8260436fe1eecd5688abea506`

## Latest completed work

Checkpoint 85 was merged to `main`. The full engine bridges target-OS audio/MIDI device enumeration through the native device monitor and carries privacy-preserving hashed identity metadata across the engine boundary.

Checkpoint 86 now has the target-OS engine/native ownership bridge, hash-only identity decoding, four independent playback and four capture slots, target-OS device target ordering/linkage for the recovered full engine, and a runtime facade/control-loop integration boundary prepared on the active branch. The bridge preserves exact selected identity, reconnect-strength semantics, topology fencing, explicit rearm, and no-default-fallback behavior.

Commit `8714e824790b35d8260436fe1eecd5688abea506` is the latest verified implementation checkpoint. All three GitHub Actions workflows completed successfully: StageForge CI, StageForge Native Device Lifecycle, and StageForge Platform Modules. StageForge CI passed Linux RT release gate, Windows x64 build/platform smoke, and macOS Apple Silicon build/platform smoke, including native-engine builds, native tests, target-OS smoke/capture evidence, and authenticated engine command dispatch.

## Next-wave selection rule

1. Prefer tasks that remove a software dependency blocking multiple backlog rows.
2. Prefer tasks that reuse already-qualified components instead of creating parallel implementations.
3. Prefer tasks that can be verified in hosted CI without pretending hosted evidence is physical qualification.
4. Keep external-hardware, licensed-product, deployment and owner-decision work explicit rather than blocking software progress that can proceed independently.
5. Preserve continuity at every meaningful checkpoint by committing code/tests/docs and updating this handoff before switching tasks.

Checkpoint 86 remains the highest-leverage task: finish recovered-engine command dispatch to the already-qualified WASAPI/CoreAudio playback/capture implementation and keep its lifecycle servicing active while the command channel is idle.

## Checkpoint 86 remaining scope

- Finish full-engine `AUDIO_ACTIVATE` and `AUDIO_INPUT_ACTIVATE` target-OS dispatch while retaining ALSA behavior on Linux.
- Bind native playback/capture callbacks to the recovered render/capture lifetime contracts.
- Update deactivate/status/drift paths for native stream state.
- Service/reconcile the native bridge regularly without violating native owner-thread requirements; the existing blocking stdin command loop must not leave topology fencing dormant during idle periods.
- Preserve exact selected-device identity, no-default-fallback behavior, topology-loss fencing and explicit rearm.
- Keep conversion/adaptation fail-closed unless an existing recovered conversion plan explicitly authorizes it.
- Add/extend full-engine target-OS smoke/contract tests for activation, capture lifecycle, loss/recovery and rejection paths where hosted endpoints permit them.
- Do not claim physical audio quality, physical hardware qualification, or live Windows endpoint behavior when the hosted runner exposes no endpoint.

## Following wave

After Checkpoint 86, select among full-engine target-OS MIDI attach/poll/event I/O; non-Linux `IsolatedPluginHost` wiring to the existing verification-to-launch binder; backlog/workbook reconciliation through the newly completed software checkpoints; or external qualification tasks when the required hardware, licensed fixtures, deployment environments or owner decisions are actually available.

## Build / verification entry points

From repository root:

```bash
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

Linux developer-alpha software gate:

```bash
python scripts/release-check.py
```

Install release-check build requirements from `requirements-release.txt` and provide Node.js.

## Important qualification boundary

Hosted/software evidence does **not** by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, Windows/macOS live endpoint behavior, or other external acceptance inputs. Keep those claims explicit and fail closed. `physicalOutputsArmed=false` remains the safe claim boundary until the required external qualification exists.

## Continuity protocol

1. At the start of work, read `PROJECT_MASTER.md`, then inspect latest commits on `main` and the active PR/branch.
2. Before substantial work, create/use a checkpoint branch rather than relying on chat state.
3. After each meaningful checkpoint, commit code/tests/docs to GitHub.
4. Before ending or when context is crowded, update this file with the new baseline, verification status, blockers, and exact next action.
5. If chat history conflicts with Git, Git wins.
6. Distinguish software/reference qualification from physical/target-environment qualification.

## Next-session handoff

- **Current checkpoint:** 86 — full-engine target-OS audio streaming integration
- **Branch / PR:** `checkpoint-86-backlog-reconcile-and-audio-stream`; PR #21 open as draft
- **Last known-good main commit:** `84f6da331a363a4638a7d17052796cbc3f861cf0`
- **Latest verified branch commit:** `8714e824790b35d8260436fe1eecd5688abea506`
- **Tests / CI:** all three workflows green for `8714e824...`; Linux, Windows x64, and macOS Apple Silicon StageForge CI jobs all passed.
- **What changed:** native bridge ownership/identity/slot work plus full-engine target linkage and runtime integration scaffolding are verified in hosted CI.
- **Open implementation issue:** the recovered command loop blocks on stdin. Native lifecycle `service()`/reconcile must continue while idle, and it must respect the native stream owner-thread contract rather than being casually moved to an unrelated service thread.
- **External evidence still needed:** physical audio quality/hardware qualification; hosted Windows may expose no usable audio endpoint; licensed plugin/deployment/owner decisions remain separate.
- **Exact next action:** modify `native/src/engine_main.cpp` to bind the native playback/capture callback adapters and target-OS activation/deactivation/status dispatch, together with a same-owner-thread periodic command/service loop so topology loss/revocation remains fail-closed during idle command periods. Then run the complete CI matrix and fix any target-OS failures before updating PR #21.

## Backup policy

The GitHub repository is the durable project backup. A checkpoint is not considered safely preserved until its source changes and this continuity record are committed to GitHub. Chat transcripts are working context, not project storage.
