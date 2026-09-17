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
- Safety branch before status mutation: `checkpoint-86-status-safety-5e81eb92`
- Engine integration commit: `fc1bf23d6370391225675cd2ae715c242b9e8090`
- Temporary original patch machinery removed: `bb822fef5956455f0899c19b4a35842721cc7738`
- Native status projection build head: `82b6e9fd7fd59ac6562d8fb0978b4b0370229312`
- Last fully green continuity head: `5e81eb92f57d4ed7de22b75fa5f7c2c602e57326`
- Status-integration patcher commit: `fdd65aa11753f7c3dae272ad8e27ace9cbac1f1c`
- Status-integration execution workflow commit: `a9cc65abcb2ccf4616501afd43de1f61818bf03f`

## Checkpoint 86 completed implementation

The branch contains the target-OS native audio ownership bridge, strict hash-only identity decoding, four independent playback and capture slots, full-engine target linkage, callback/request/runtime adapters, bounded target-OS stdin readiness, and a same-owner-thread service-loop primitive. The lifecycle contract preserves exact selected identity, topology fencing, explicit rearm, no default endpoint substitution, and fail-closed unsupported conversion behavior.

`native/src/engine_main.cpp` is wired to the CP86 runtime on Windows/macOS. Commit `fc1bf23d6370391225675cd2ae715c242b9e8090` adds the native runtime/includes, bounded stdin service, target-OS playback/capture activation through exact selected identity tokens, native close paths for deactivate/shutdown, and native-running drift fencing while retaining Linux ALSA behavior.

The engine-wired branch and typed status projection are verified green at `5e81eb92f57d4ed7de22b75fa5f7c2c602e57326`: StageForge CI `35237441286`, Native Device Lifecycle `35237441287`, and Platform Modules `35237441283` all completed successfully.

Status projection work through `82b6e9fd7fd59ac6562d8fb0978b4b0370229312` adds typed `EndpointStreamStats` projection plus smoke coverage and build integration. Native `discontinuities` are separate and are never relabeled as ALSA xruns.

A deterministic follow-up patcher was committed in `fdd65aa11753f7c3dae272ad8e27ace9cbac1f1c`. It wires projected native playback/capture status into `AUDIO_INPUT_STATUS`, `AUDIO_STREAM_STATUS`, and global `STATUS`, keeps native `xruns=0`, reports native discontinuities separately, treats native render callbacks as valid rate-measurement activity, and leaves ALSA write-timing fields zero for native execution. Commit `a9cc65abcb2ccf4616501afd43de1f61818bf03f` temporarily extends the already-registered StageForge CI workflow to execute and commit that deterministic source mutation on the active branch. This is execution machinery, not intended production infrastructure.

These changes intentionally do not claim live endpoint qualification. `physicalOutputsArmed=false` remains the safe claim boundary.

## Verification state

- Fully green pre-mutation head: `5e81eb92f57d4ed7de22b75fa5f7c2c602e57326`.
- New CI for `a9cc65abcb2ccf4616501afd43de1f61818bf03f` is running: StageForge CI `35243997245`, Native Device Lifecycle `35243997356`, Platform Modules `35243997258`.
- The StageForge CI run contains a dedicated `Apply CP86 native status integration` job. Do not call the generated engine mutation verified until that job commits the source and the subsequent head completes all three required workflows.

## Remaining Checkpoint 86 scope

- Observe the status-apply job, confirm the generated `engine_main.cpp` commit, then remove `scripts/apply-cp86-status-integration.py` and restore `.github/workflows/ci.yml` to read-only production CI permissions/content.
- Add/extend full-engine command smoke coverage for target-OS rejection and hosted-safe status/lifecycle behavior.
- Run all three required workflows on the cleaned final CP86 head and fix any target-OS failures.
- Reconcile AUD-035/AUD-036/DEV-033/DEV-034 against their exact acceptance criteria before marking rows Done.

## Following wave

After Checkpoint 86, continue directly into the highest-leverage unresolved software dependency. Current evidence points to target-OS MIDI attach/poll/event I/O: target-OS MIDI enumeration/identity exists, while full-engine `MIDI_ATTACH`/`MIDI_INPUT_POLL` still depend on the recovered `MidiInputManager` execution path. Non-Linux `IsolatedPluginHost` verification-to-launch wiring remains another known software candidate and must be ordered by the formal backlog acceptance criteria.

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

Hosted/software evidence does not by itself qualify physical audio/MIDI hardware, licensed plugins, deployed services, installed packages, live Windows/macOS endpoint behavior, or audio quality. Hosted Windows may expose no usable endpoint. Capture packet discontinuity metadata is not currently consumed by the recovered engine capture callback. Native endpoint discontinuities are not ALSA xruns. `physicalOutputsArmed=false` remains unchanged.

## Continuity protocol

1. Read this file and inspect current branch/PR history before substantive work.
2. Create a safety/checkpoint branch before substantial mutations.
3. Commit each meaningful implementation/test/documentation checkpoint to GitHub.
4. Verify CI before calling a checkpoint known-good.
5. Update this file before ending or when context is crowded.
6. If chat conflicts with Git, Git wins.

## Exact next action

Inspect StageForge CI run `35243997245`, especially job `Apply CP86 native status integration`. Confirm the branch advances with `Wire native audio status into full engine`. Then inspect the generated `native/src/engine_main.cpp`, remove the temporary patcher and CI write job/permissions, add hosted-safe full-engine command smoke assertions for native status/rejection behavior, and require StageForge CI, Platform Modules, and Native Device Lifecycle green on the cleaned head. Reconcile AUD-035/AUD-036/DEV-033/DEV-034 immediately afterward and continue into target-OS MIDI attach/poll/event I/O if still open.