# Checkpoint 84 source consolidation

Input: StageForge-Astra-Backlog-Checkpoint-69.zip, supplied by the owner.
SHA-256: 023cbaefef19f07fc95acf7119c8cfa40cc047267727e2bc5ed64fb49df7a10c.
The archive has 592 files. Paths and symlink attributes were checked before
separate extraction. This digest identifies the received file; it is not an
independent publisher attestation.

Base: GitHub main 915373bd3fb871da03d8e340ae869e024acac46b (Checkpoint 83).
586 paths were absent from that checkout and restored. The identical session
channel and newer local IPC, Windows named-pipe and audio evidence modules were
preserved. README was rewritten. The conflicting native CMake entry points were
combined: root builds include the engine and supported OS device components,
while device-only CI retains its existing entry point.

The placeholder CI was removed. Recovered full-engine Linux release and Windows /
macOS build tests now run alongside the existing platform and lifecycle evidence.
Historical archive claims of 654 tests are not fresh consolidation evidence.

Source access is resolved. The four software backlog rows remain In Progress:
AUD-035/036 and DEV-033/034 require actual engine/device integration. Physical
hardware, licensed plugins, deployment, package and owner decisions remain
separate. No recovered historical workbook replaces the Checkpoint 83 master.
