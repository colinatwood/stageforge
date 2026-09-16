# StageForge Master Project File

> Canonical continuity record for development sessions. Git remains the source of truth; this file is the compact handoff point when chat/session context runs out.

## Current baseline

- Repository: `colinatwood/stageforge`
- Canonical branch: `main`
- Last known-good main commit: `84f6da331a363a4638a7d17052796cbc3f861cf0`
- Latest completed milestone: **Checkpoint 85 — bridge native target-OS devices into full engine**
- Active work: **Checkpoint 86 — full-engine target-OS audio streaming integration**
- Active branch: `checkpoint-86-backlog-reconcile-and-audio-stream`

## Latest completed work

Checkpoint 85 was merged to `main`. The full engine bridges target-OS audio/MIDI device enumeration through the native device monitor and carries privacy-preserving hashed identity metadata across the engine boundary. The checkpoint includes full-engine target-OS enumeration qualification and tests that reject leaked/malformed identity metadata.

Checkpoint 84 consolidated the recovered Checkpoint 69 engine/backend/frontend/schemas/packaging/tests with Checkpoint 70–83 platform work. Source access is no longer a blocker.

## Next-wave selection rule

Choose work by this order:

1. Prefer tasks that remove a software dependency blocking multiple backlog rows.
2. Prefer tasks that reuse already-qualified components instead of creating parallel implementations.
3. Prefer tasks that can be verified in hosted CI without pretending hosted evidence is physical qualification.
4. Keep external-hardware, licensed-product, deployment and owner-decision work explicit rather than blocking software progress that can proceed independently.
5. Preserve continuity at every meaningful checkpoint by committing code/tests/docs and updating this handoff before switching tasks.

Using that rule, Checkpoint 86 targets the engine audio execution bridge before MIDI I/O, plugin-host integration, or external qualification. The native WASAPI/CoreAudio playback/capture, endpoint pinning, topology fencing, explicit rearm and capability probing already exist; the recovered engine still rejects non-ALSA `AUDIO_ACTIVATE` and capture paths. Connecting those layers has the highest immediate reuse and backlog impact.

## Checkpoint 86 scope

- Wire full-engine `AUDIO_ACTIVATE` to the qualified target-OS native audio path on Windows/macOS while retaining ALSA behavior on Linux.
- Integrate the recovered engine capture-buffer/lifetime contract with native capture.
- Preserve exact selected-device identity, no-default-fallback behavior, topology-loss fencing and explicit rearm.
- Keep conversion/adaptation fail-closed unless an existing recovered conversion plan explicitly authorizes it.
- Add full-engine target-OS smoke/contract tests for activation, capture lifecycle, loss/recovery and rejection paths where hosted endpoints permit them.
- Do not claim physical audio quality, physical hardware qualification, or live Windows endpoint behavior when the hosted runner exposes no endpoint.

## Following wave

After Checkpoint 86, select among:

- full-engine target-OS MIDI attach/poll/event I/O;
- non-Linux `IsolatedPluginHost` wiring to the existing verification-to-launch binder;
- backlog/workbook reconciliation through the newly completed software checkpoints;
- external qualification tasks when the required hardware, licensed fixtures, deployment environments or owner decisions are actually available.

The selection rule above decides between them based on dependency removal and available evidence rather than checkpoint numbering alone.

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

Hosted/software evidence does **not** by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, Windows/macOS runtime behavior, or other external acceptance inputs. Keep those claims explicit and fail closed. See `docs/remaining-data-requirements.md` and the external qualification tooling/evidence workflow before closing hardware/platform backlog items.

## Continuity protocol

1. **At the start of work:** read `PROJECT_MASTER.md`, then inspect the latest commits on `main` and any active PR/branch.
2. **Before substantial work:** create/use a checkpoint branch rather than relying on chat state.
3. **After each meaningful checkpoint:** commit code/tests/docs to GitHub. Do not leave the only copy of progress in chat.
4. **Before ending or when context is getting crowded:** update this file with the new baseline commit, completed checkpoint, verification status, unresolved blockers, and exact next action; commit that update.
5. **Recovery rule:** if chat history conflicts with Git, Git wins.
6. **No false completion:** distinguish software/reference qualification from physical/target-environment qualification.

## Next-session handoff

- **Current checkpoint:** 86 — full-engine target-OS audio streaming integration
- **Branch / PR:** `checkpoint-86-backlog-reconcile-and-audio-stream`; PR not opened yet
- **Last known-good commit:** `84f6da331a363a4638a7d17052796cbc3f861cf0` on `main`
- **Tests run / result:** no Checkpoint 86 implementation tests yet; branch started from known-good Checkpoint 85 + continuity commit
- **What changed:** selected the next-wave task using dependency removal/reuse/CI-verifiability criteria and persisted its exact scope before implementation
- **Open blockers / external evidence needed:** hosted Windows may expose no audio endpoint; physical audio quality/hardware qualification remains external; licensed plugin/deployment/owner decisions remain separate
- **Exact next action:** map the existing target-OS native playback/capture ownership API into `native/src/engine_main.cpp` `AUDIO_ACTIVATE`/capture lifecycle, then add fail-closed full-engine tests before broadening scope

## Backup policy

The GitHub repository is the durable project backup. A checkpoint is not considered safely preserved until its source changes and this continuity record (when the handoff changes) are committed to GitHub. Chat transcripts are working context, not project storage.
