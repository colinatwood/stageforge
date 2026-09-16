# Core 4.2 operational boundary

Core 4.2 adds a bounded Unix-domain transport for authenticated UPPF frames, durable tamper-evident local identity/session state, a browser profile editor with projection visibility, an isolated effect-host watchdog, platform qualification probes, and Linux service packaging.

The Unix socket is mode `0600`, each connection has bounded requests and timeouts, frame sizes are checked before allocation, and UPPF still performs session, sequence, epoch, capability and HMAC verification. Checkpoint 59 factors the same length-prefixed authenticated framing onto message transports and defines a Windows `AF_PIPE` server contract that refuses startup without positive ACL validation. Real Windows DACL creation/inspection and client/server execution remain the portability boundary; Linux tests do not qualify those Windows security semantics.

VST3, CLAP, LV2 and Audio Unit remain adapter formats. Core never loads their SDK/runtime into its real-time process. An external format becomes operational only when a separately installed adapter executable completes the host contract. Missing, crashed, malformed or timed-out hosts are bypassed.

The qualification probe reports discovery only. An audio device, BlueZ controller, or serial UWB endpoint is never called qualified until the hardware bench records real measurements and identities. LE Audio carries program media; UWB supplies independent ranging/clock evidence. Neither discovery nor a synchronization plan arms outputs.

Canonical audio remains planar float32 at 192 kHz. Rate conversion normalizes graph execution but cannot recreate bandwidth or detail absent from the source.
