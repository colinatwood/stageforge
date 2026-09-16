# Developer-alpha known issues

- Local Linux is the only release target. Windows/macOS USB plus audio-endpoint/installed-driver evidence adapters and persistence-grade identity contracts have fixture/integration coverage only; platform enumeration/hotplug/stream behavior has not been exercised on those operating systems.
- Physical hardware, latency, audible playback/recording, LE Audio and UWB timing are unqualified and deferred.
- Local/proxy HTTP security hardening is implemented, but the intended venue/control LAN still needs real TLS certificate, reverse-proxy, IdP, firewall and browser-network qualification.
- Fenced-node recovery requires the original configured witness quorum to authorize the exact persisted transfer. Corrupt, replaced, stale or unverifiable fence evidence remains deliberately fenced and requires an offline incident procedure.
- Audio activation requires a numeric ALSA hardware endpoint and an explicit conversion policy when configured format/rate/channel layout differs. Linux integer/multichannel execution is implemented, but converter quality and named-hardware behavior remain unqualified.
- MIDI automatic rebind requires a serial-backed identity. Topology-only devices require explicit rebind.
- The reviewed driver catalog is intentionally small (currently RME Babyface Pro FS plus Focusrite Scarlett Solo/2i2/4i4 4th Gen Windows package metadata); search links and catalog records are not hardware compatibility or qualification claims.
- Checkpoints 54 and 62 complete real-Chromium rendered/responsive and accessibility-tree reference acceptance through an asset/API bridge because managed Chromium still blocks direct loopback navigation. Actual screen-reader/switch/voice assistive-technology and deployed browser-to-LAN/TLS/IdP qualification remain open.
- Plugin delay alignment and atomic effect/delay transactions are connected to the native render path. Automatic overload shedding remains disabled: overload recommendations still require an explicit, authority-checked transaction request, and real plugin behavior is unqualified.
- Polyphonic streaming has software coverage, but simultaneous long-loop disk throughput, audible starvation behavior and cancellation timing remain unqualified on real storage/audio hardware.
- No project license has been selected, so publication remains blocked.
