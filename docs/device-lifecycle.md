# Native device monitor: Checkpoint 74

The `stageforge_devices` C++ library adds Windows MMDevice enumeration and
notifications plus macOS CoreAudio HAL enumeration and property listeners.
It is a standalone control-thread module. The full StageForge audio engine and
prior Python lifecycle reconciler are not in this repository, so integration
with those components remains open.

Create, start, snapshot, stop, and destroy a monitor on the same control thread.
Windows construction requires COM MTA initialization to succeed. `start()` and
`stop()` are idempotent. Taking a snapshot while stopped is rejected. Start
subscribes before snapshots so callers can compare `revision()` before and after
reading and retry if topology changed. Snapshots are observations, not an atomic
transaction across device count and default selection.

OS callbacks only increment a process-wide atomic topology revision. They never
open streams, allocate work, invoke user code, or reselect devices. Revision
changes can reflect another active monitor's subscription. Control code should
refresh its snapshot on revision changes; the audio callback must not enumerate.
Callback storage survives monitor teardown to avoid late-callback use-after-free.
Explicit `stop()` reports unregistration errors; destructor cleanup failure
terminates rather than silently reporting successful cleanup.

Windows observes endpoint addition/removal, state, default and property changes.
macOS observes the system device list and default input/output changes; per-device
sample-rate, alive-state and stream-configuration listeners are not implemented.
No raw endpoint identifiers or device names are exported by this module.

## Hosted evidence

[Initial hosted run](https://github.com/colinatwood/stageforge/actions/runs/34872014161)
compiled and passed CTest plus the evidence executable on both target OSes.
Test merge source SHA: `e89241b4c3f67e4c90ea557d22404ed4fde6263e`.

| Observation | Windows x64 | macOS 14 arm64 |
| --- | --- | --- |
| Explicit lifecycle cycles | 25 passed | 25 passed |
| Device count | 0 | 3 |
| Input/output default present | false / false | true / true |
| Lifecycle check elapsed | 0.220057 s | 0.244314 s |
| Inactive snapshot and wrong-thread rejection | passed | passed |
| Destruction while subscribed | passed | passed |
| Observed notification revision | 0 | 0 |

These are real OS enumeration, registration, unregistration and restart results.
No notification was observed; event delivery is unverified. The durations include
all cycles and brief idle waits, not an audio latency or real-time guarantee.
The workflow uploads JSON with exact executable/source SHA-256 and source commit.

## Remaining implementation and qualification

- Integrate snapshots/revisions with the full engine lifecycle reconciler.
- Persistent identity selection and explicit recovery policy.
- WASAPI and CoreAudio stream format negotiation, start/stop and loss handling.
- Native event delivery tests, per-device macOS property listeners and race tests.
- Physical disconnect/reconnect, real audio performance and hardware qualification.
- Licensed plugin compatibility remains a separate gate.

Every new evidence record sets `physicalOutputsArmed`, `physicalHardwareQualified`,
`audioStreamingQualified` and `physicalHotplugQualified` to false.

## Build

On Windows with MSVC/CMake or macOS with Xcode command-line tools/CMake:

```sh
cmake -S native -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

API references:
[Microsoft notification ownership](https://learn.microsoft.com/en-us/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-immdeviceenumerator-registerendpointnotificationcallback),
[Apple property listeners](https://developer.apple.com/documentation/coreaudio/audioobjectaddpropertylistener(_:_:_:_:)).
