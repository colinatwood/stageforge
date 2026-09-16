# Core 4.5 DAW production services

The dependency-free reference renderer resolves the portable arrangement into stereo 192 kHz audio. It performs source-rate conversion, non-destructive offsets, fades, volume automation, equal-power pan, summing, peak limiting, deterministic TPDF dither, PCM export and receipt hashing. Jobs are confined to the export directory and bounded to 30 seconds; a production streaming renderer should implement the same receipt contract for longer material.

Media ingest is content-addressed and confined to the import directory. Recording is a two-stage contract: Core prepares an unarmed take plan, while an authenticated capture adapter arms hardware and supplies a finalized WAV plus dropout evidence. Core never infers a clean take from a filename.

Tempo changes map musical beats to canonical frames without changing Show Time. Routing, sends and automation remain portable intent. The native real-time graph and isolated plugin host remain the execution boundaries; external CLAP, VST3, LV2 and Audio Unit binaries require explicit absolute executable adapters implementing the newline-delimited host protocol. Activation protocol 1 requires exact plugin/format identity, process capability and a bounded latency declaration from 0 through 65,536 canonical frames. Every response echoes its request ID. Adapters launch directly without a shell, remain watchdog-bounded, and still require format/platform qualification.

Autosaves retain the newest 20 normalized revisions. Render preflight checks disk capacity, non-finite samples become silence, output is limited, and reduced-bit exports use deterministic dither when a seed is fixed.
