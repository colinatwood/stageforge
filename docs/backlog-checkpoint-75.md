# Checkpoint 75 master backlog amendment

Checkpoint 75 merge commit: `17ba67978313b822c692e3c4eeb39fd68a8c2421`.

The master backlog remains **25 open, 22 P0, 4 software, 19 qualification,
2 decisions**. No row is closed by this checkpoint.

## Narrowed rows

| Item | Status | Checkpoint 75 progress | Remaining exit |
| --- | --- | --- | --- |
| DEV-033 | In Progress | Native Windows MMDevice monitor builds with fail-closed hashed identity reconciliation. SDK capability detection refuses to pretend StableId support under SDK 26100. | Active Windows endpoint + newer-SDK StableId evidence, native Windows MIDI topology, and full-engine stream fencing/reselection. |
| DEV-034 | In Progress | Apple Silicon hosted CI proves CoreAudio and CoreMIDI software topology add/remove/recreate notifications, hashed strong identity detach, and exact-unique recovery under AddressSanitizer. | Feed those native events/identity decisions into full-engine unsafe-stream fencing and explicit recovery/rearm; physical hotplug remains DEV-035. |

AUD-035 and AUD-036 remain In Progress. No stream is opened by Checkpoint 75.
DEV-035 remains Deferred for named physical-device hotplug qualification.

## Evidence

Successful source head `8028ac5005e81ddd6f69a8df2bfed0a28ee7e313`:
- CI run `34881629544`: passed
- Platform Modules run `34881629490`: passed
- Native Device Lifecycle run `34881629489`: Windows + macOS passed
- macOS lifecycle artifact digest: `sha256:08ed7bea660a89e1140eb02bfc96dac8775987d5c1e1a7f735b78bd7b8433d03`
- Windows lifecycle artifact digest: `sha256:6b3902bed5602f5b9ccf73307d33c518cbbf80910a43605780b7398f59e3f6dd`

The final documentation head `dda1d5d99b029ddd8b88acde439d2c59af71c1fe`
also passed all three workflows before merge.

Every Checkpoint 75 evidence envelope keeps physical outputs, physical hardware,
audio streaming, and physical hotplug unqualified.
