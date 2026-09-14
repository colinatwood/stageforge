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
Checkpoint 75 adds domain-separated SHA-256 identity records: Windows endpoint
IDs are explicitly installation-scoped (not PKEY_AudioEndpoint_StableId), while
macOS records represent CoreAudio device UIDs. No automatic reconnect decision
is implied by a hash. Native SHA-256 is checked against an independent known
vector on both OSes, including domain separation and empty-identity rejection.

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
- Windows native event delivery, per-device macOS property listeners and race tests.
- Physical disconnect/reconnect, real audio performance and hardware qualification.
- Licensed plugin compatibility remains a separate gate.

Every new evidence record sets `physicalOutputsArmed`, `physicalHardwareQualified`,
`audioStreamingQualified` and `physicalHotplugQualified` to false.

## Checkpoint 75 CoreAudio events

[Hosted run 34875161016](https://github.com/colinatwood/stageforge/actions/runs/34875161016)
passed on code `1298c00e908923f18cb24198fc98d417394eb9d3` (test merge
`d3142df77d08df82e373251922d59042cb0ec8cd`). Windows passed one CTest and macOS
passed two. The macOS event executable recorded four transitions and all fixture
checks true. Evidence JSON is retained under `docs/evidence/checkpoint-75/`.

`coreaudio_device_events` creates a process-private empty aggregate device through
CoreAudio, waits for a real notification revision and its hashed UID to appear,
destroys it, then waits for another revision and disappearance. It repeats after
listener stop/restart using the same UID, proving OS UID/hash continuity across
software-device recreation. The fixture verifies its subdevice list is empty.
It never configures an I/O callback, tap, underlying audio device, or stream.
Raw fixture UIDs are not recorded in the evidence artifact.

The native lifecycle runner still proves 25 stop/restart cycles on both OSes.
macOS now adds an OS event test, not a callback invoked by the test itself. This
narrows DEV-034; physical hotplug, CoreMIDI, stream loss/recovery and full-engine
integration remain open. Windows hosts without endpoints test empty enumeration
and the hash contract, but do not establish real-endpoint ID extraction or native
event delivery. Do not treat those absent paths as passed.

Snapshots may fail if topology changes during a UID read. Callers must fail closed
and refresh off the audio thread; this API does not authorize output or guarantee
an atomic topology transaction.

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
