# StageForge Master Project File

> Canonical continuity record. Git is the source of truth; this file is the compact handoff when chat/session context disappears.

## Current baseline

- Repository: `colinatwood/stageforge`
- Canonical branch: `main`
- Content-equivalent known-good main tree: `46ecfb0e334f82bc3bafde7daa46d1336136bb28` (temporary CP86 runner was added then removed; current main commit `e7f44518175fe513fdd69cdde116c60409a46f29` restores the prior tree exactly).
- Latest completed milestone: **Checkpoint 85 — bridge native target-OS devices into full engine**
- Active work: **Checkpoint 86 — full-engine target-OS audio streaming integration**
- Active branch: `checkpoint-86-backlog-reconcile-and-audio-stream`
- Active PR: **#21 — Checkpoint 86: integrate full-engine target-OS audio streaming**
- Safety branch before this wave: `checkpoint-86-safety-848d28a`
- Engine integration commit: `fc1bf23d6370391225675cd2ae715c242b9e8090`
- Current branch cleanup head before this continuity update: `bb822fef5956455f0899c19b4a35842721cc7738`

## Checkpoint 86 completed implementation

The branch contains the target-OS native audio ownership bridge, strict hash-only identity decoding, four independent playback and capture slots, full-engine target linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, and a same-owner-thread service-loop primitive. The lifecycle contract preserves exact selected identity, topology fencing, explicit rearm, no default endpoint substitution, and fail-closed unsupported conversion behavior.

`native/src/engine_main.cpp` is now actually wired to the CP86 runtime on Windows/macOS. Commit `fc1bf23d6370391225675cd2ae715c242b9e8090` adds the native runtime/includes, bounded stdin service, target-OS playback/capture activation through exact selected identity tokens, native close paths for deactivate/shutdown, and native-running drift fencing while retaining Linux ALSA behavior.

The deterministic patch machinery used to land the large engine mutation was removed from the active branch in `bb822fef5956455f0899c19b4a35842721cc7738`. A temporary default-branch runner was also removed, restoring main's prior tree exactly. Do not reintroduce self-modifying CI as production infrastructure.

These changes intentionally do not claim live endpoint qualification. `physicalOutputsArmed=false` remains the safe claim boundary.

## Remaining Checkpoint 86 scope

- Report native playback/capture status from `EndpointStreamStats`, including verified configuration and discontinuities without mislabeling them as ALSA xruns.
- Include native execution in global `STATUS` aggregation.
- Add/extend full-engine command smoke coverage for target-OS rejection and hosted-safe lifecycle behavior.
- Complete the CI matrix on the engine-wired branch and fix target-OS failures before treating the wave as verified. CI was queued on `bb822fef...` when this record was updated; do not call it green until conclusions are observed.

## Following wave

After Checkpoint 86, choose the highest-leverage remaining software dependency from the canonical backlog. Current known candidates are target-OS MIDI attach/poll/event I/O and non-Linux `IsolatedPluginHost` verification-to-launch wiring. Reconcile exact AUD-035/AUD-036/DEV-033/DEV-034 acceptance criteria before marking rows Done. External hardware, licensed-product, deployment, package and owner-decision qualification remain separate until their evidence exists.

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

Hosted/software evidence does not by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, live Windows/macOS endpoint behavior, or audio quality. Hosted Windows may expose no usable endpoint. Capture packet discontinuity metadata is not currently consumed by the recovered engine capture callback. Keep those limitations explicit. Native endpoint discontinuities are not ALSA xruns. `physicalOutputsArmed=false` remains unchanged.

## Continuity protocol

1. Read this file and inspect current branch/PR history before substantive work.
2. Create a safety/checkpoint branch before substantial mutations.
3. Commit each meaningful implementation/test/documentation checkpoint to GitHub.
4. Verify CI before calling a checkpoint known-good.
5. Update this file before ending or when context is crowded.
6. If chat conflicts with Git, Git wins.

## Exact next action

Inspect StageForge CI run `35231482352` plus the matching Platform Modules and Native Device Lifecycle runs for `bb822fef5956455f0899c19b4a35842721cc7738`. Fix any compile/test failure from the engine integration. Once green, add native `AUDIO_INPUT_STATUS`, `AUDIO_STREAM_STATUS`, and global `STATUS` reporting using `EngineNativeAudioRuntime`/`EndpointStreamStats`, with native discontinuities reported separately and `xruns=0`; add hosted-safe full-engine command coverage; rerun all required CI. Then reconcile the four formal software rows and continue directly into the next unresolved software item, expected to be target-OS MIDI attach/poll/event I/O if its acceptance criteria remain open.
