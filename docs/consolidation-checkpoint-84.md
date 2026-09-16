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

## Integration audit findings

- Archive executable bits are restored in Git for 20 scripts. Windows extraction
  alone does not preserve the Unix execution contract used by installed launchers.
- Recovered `docs/current-backlog.md` is labeled historical to avoid conflicting
  with the newer master. License notes now acknowledge the existing LICENSE,
  without inventing owner approval for the recovered distribution.
- The recovered `IsolatedPluginHost` still refuses non-Linux external launch.
  Checkpoint 73's tested `platform_launch_binding` module is present, but its
  process streams and cleanup lifetime are not wired into that host. PLUG-034
  remains the hosted binder result; end-to-end host compatibility is not proven.
- Root builds compile both engine and device components on supported OSes.
  Compilation in one checkout is not a runtime bridge: engine audio and the
  newer native endpoint stream still need a shared control/callback integration.
