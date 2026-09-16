# Audio identity and hotplug observation

The bridge scans native audio endpoints every two seconds while the native engine
is available. It publishes a monotonic generation and a bounded history of 128
connect/disconnect and same-native-ID identity-change observations at
`GET /api/v1/audio/hotplug?after=<generation>`.
Scanning and reselection never activate capture or playback.

On Linux, an ALSA hardware address is resolved through sound-class sysfs. A USB
endpoint with VID, PID and a hardware serial receives a privacy-preserving
persistent identifier derived from those values plus its PCM endpoint and direction.
The serial itself is not returned or stored. If ALSA renumbers the card, exactly one
matching serial-backed endpoint may replace the prior native ID for selection.

USB devices without serials receive topology identity. ALSA aliases and endpoints
without resolvable hardware evidence remain volatile. Neither class is eligible for
automatic reconnect; the operator must use the existing explicitly acknowledged
recovery action.

Even a strong identity match only restores the selected execution endpoint. It does
not restart a stream, restore authority, arm physical output, or bypass audio
constraint preflight. Explicit playback/capture and recovery acknowledgements remain
mandatory.

## Limits

This is Linux identity evidence, not Windows Core Audio or macOS Core Audio device
identity. Some devices expose duplicated or unreliable serial strings, and composite
devices can change PCM endpoint layout after firmware updates. Those cases require
real hardware fixtures and vendor-specific qualification before broader automatic
reconnect claims are appropriate.

## Identity reuse hardening

Scans retain the first recorded identity for each native endpoint ID. A changed
serial at that ID cannot overwrite the record. Serial resolution requires exactly
one matching connected endpoint, even when the original numeric ID exists.
Unchanged observations no longer rewrite the identity file every two seconds.

When a connected endpoint's persistent identity changes at the same native ID, the
bridge emits `identity-changed` with both privacy-preserving identifiers and stops
active streams using that ID. Repeated scans of the same replacement do not repeat
the event.

An operator may choose **Trust as output/input replacement** in the device UI or
call `POST /api/v1/audio/identity/rebind` with the old desired ID, connected current
ID, direction, and `acknowledgeIdentityReplacement: true`. All streams in that
direction must already be stopped. The stored trust remains bound to the exact
persistent identity and unique matching endpoint. The operation may restore native
selection, but returns `streamsStarted: false` and `physicalOutputsArmed: false`.
Topology identity still cannot distinguish different devices moved onto exactly the
same topology, so the operator must verify the choice.

## Stream lifecycle

Discovery scans, endpoint selection, activation, recovery, deactivation and
authority fencing share one control lock. When a scan loses an endpoint selected by
an active ALSA stream, the bridge stops that output or input before selecting a
replacement. The disconnect observation reports the stopped slot numbers. A serial
match may then restore selection, but stream activation still needs the existing
operator acknowledgement and preflight.
