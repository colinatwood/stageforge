# StageForge Master Project File

> Canonical continuity record. Git is the source of truth; this file is the compact handoff when chat/session context disappears.

## Current baseline

- Repository: `colinatwood/stageforge`
- Canonical branch: `main`
- Last known-good main: `84f6da331a363a4638a7d17052796cbc3f861cf0`
- Latest completed milestone: **Checkpoint 85 — bridge native target-OS devices into full engine**
- Active work: **Checkpoint 86 — full-engine target-OS audio streaming integration**
- Active branch: `checkpoint-86-backlog-reconcile-and-audio-stream`
- Active PR: **#21 — Checkpoint 86: integrate full-engine target-OS audio streaming**
- Safety branch before this wave: `checkpoint-86-safety-848d28a`
- Last fully verified implementation before this wave: `07d7006c3f24e89164bb30e53a417db47d7d2ed7`
- Current five-item wave head before this continuity commit: `ce919d34abd6cfe1cc4a9be27a38aff2a1e4d08d`
- CI for the new wave was queued when this handoff was written; do not call it verified until all required workflows are green.

## Checkpoint 86 completed implementation

The branch contains the target-OS native audio ownership bridge, strict hash-only identity decoding, four independent playback and capture slots, full-engine target linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, and a same-owner-thread service-loop primitive. The lifecycle contract preserves exact selected identity, topology fencing, explicit rearm, no default endpoint substitution, and fail-closed unsupported conversion behavior.

The latest five-item backlog wave added:

1. `engine_native_audio_command.h`: normalized command-facing native playback/capture activation and status result contract.
2. `engine_native_audio_command.cpp`: runtime-to-command result mapping using verified native configuration and fail-closed callback/running state.
3. `engine_native_audio_command_smoke.cpp`: hosted-safe invalid-slot and failed-activation coverage without requiring a physical endpoint.
4. `native/devices.cmake`: builds the command adapter and registers its smoke in the target-OS device test matrix.
5. This continuity checkpoint, preserving exact head, verification state, and next action.

These changes intentionally do not claim live endpoint qualification. `physicalOutputsArmed=false` remains the safe claim boundary.

## Remaining Checkpoint 86 scope

- Wire `native/src/engine_main.cpp` to the native command/runtime adapter on Windows/macOS while retaining ALSA behavior on Linux.
- Replace target-OS blocking stdin behavior with bounded readiness plus same-owner-thread `native_audio.service(0)` during idle periods.
- Dispatch target-OS `AUDIO_ACTIVATE` and `AUDIO_INPUT_ACTIVATE` using the exact selected device identity token and existing render/capture callbacks.
- Close native playback/capture from deactivate and shutdown paths.
- Report native playback/capture status from `EndpointStreamStats`, including verified configuration and discontinuities without mislabeling them as ALSA xruns.
- Include native execution in global `STATUS` and reject drift reconfiguration while a native playback slot is running.
- Add/extend full-engine command smoke coverage for target-OS rejection and hosted-safe lifecycle behavior.
- Run the complete CI matrix and fix target-OS failures before treating the wave as verified.

## Following wave

After Checkpoint 86, choose the highest-leverage software dependency among target-OS MIDI attach/poll/event I/O, non-Linux `IsolatedPluginHost` verification-to-launch wiring, and backlog/workbook reconciliation. External hardware, licensed-product, deployment, package and owner-decision qualification remain separate until their evidence exists.

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

Hosted/software evidence does not by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, live Windows/macOS endpoint behavior, or audio quality. Hosted Windows may expose no usable endpoint. Capture packet discontinuity metadata is not currently consumed by the recovered engine capture callback. Keep those limitations explicit. `physicalOutputsArmed=false` remains unchanged.

## Continuity protocol

1. Read this file and inspect current branch/PR history before substantive work.
2. Create a safety/checkpoint branch before substantial mutations.
3. Commit each meaningful implementation/test/documentation checkpoint to GitHub.
4. Verify CI before calling a checkpoint known-good.
5. Update this file before ending or when context is crowded.
6. If chat conflicts with Git, Git wins.

## Exact next action

First inspect CI for `ce919d34...` and fix any command-adapter build/test failure. Once green, edit `native/src/engine_main.cpp` to include the target-OS native audio runtime/command and bounded stdin interfaces; instantiate `EngineNativeAudioRuntime`; service it on the command-owner thread during bounded stdin waits; then wire target-OS playback/capture activate, deactivate, status, drift guard, global status, and shutdown paths. Preserve Linux ALSA behavior and all fail-closed identity/rearm boundaries.
