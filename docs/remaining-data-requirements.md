# Remaining inputs required for backlog completion

The current repository contains the platform modules and native lifecycle work,
not the complete StageForge engine, frontend, converters or Linux packaging tree.
The referenced "Continue Soundforge Work" conversation reports exporting a
takeover bundle containing the last full Checkpoint 69 source, checksums and
HANDOFF.md. That archive is not attached to the accessible conversation record
and was not found among StageForge-named files in Desktop or Downloads. Its
location has been requested. Do not reconstruct missing engine contracts from
the names of backlog rows or overwrite the newer GitHub platform implementation.

| Work | Required input or environment |
| --- | --- |
| AUD-035/036, DEV-033/034 integration | Full-source takeover bundle, including Checkpoint 58 shared runtime fencing and AUD-033 conversion implementation, to connect native streams to the actual engine. |
| Windows endpoint validation | A Windows host with an accessible audio endpoint. GitHub-hosted runs currently report zero playback/capture endpoints. Native MIDI enumeration sees one endpoint, but no PnP event was observed. |
| Capture validation | An authorized input environment and the engine's capture-buffer/lifetime contract. A separate read-only CI report records microphone authorization without requesting it or capturing audio. |
| AUD-034 | Actual conversion implementation and accepted reference-signal/measurement envelope. No invented quality figures. |
| UX-035 | The actual frontend/operator workflows and a selected assistive-technology environment. |
| PKG-033/034 | Package source, package artifacts and installed-service/device-permission qualifier from the full tree; then a clean target host with the required device namespaces. |
| REC-033/034, SEC-039, HW-037 | Independent witness/node hosts, clock/custody information, and declared power/network failure domains. Hosted jobs are not proof of physical independence. |
| SEC-040 | Actual deployment URL, TLS/proxy/IdP/firewall configuration and authorized workload/failure-injection environment. |
| PLUG-033, PLUG-035/036/038 | Selected product/version/OS/architecture matrix, licensed fixtures and permission to run the qualification cases. |
| LEGAL-001, PLUG-037 | Owner-approved license and fixture redistribution/automation terms. Apache-2.0 exists in this repository; consistency with unavailable packaged notices is not established. |
| DEV-035, LIVE-033, HW-033/034/035/036 | Named devices, physical routing/loopback or controller/RF environments, and agreed timing/audible measurement conditions. |

These are limits on completing the corresponding acceptance criteria. They do
not turn hosted software tests into physical hardware or product qualification.
The four software rows remain In Progress; existing qualification/decision
statuses are preserved until their evidence or owner decisions are supplied.
