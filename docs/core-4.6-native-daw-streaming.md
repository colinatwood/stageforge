# Core 4.6 native DAW streaming

The native streaming kernel operates on fixed compile-time region and block capacities. Source, effect, progress and sink adapters are callbacks; the render loop performs no discovery, file opening or allocation. Cancellation is an atomic flag and every block advances observable progress only after the sink accepts it.

The backend WAV adapter mirrors the native contract in 1,024-frame blocks and completes through an atomic rename. Media reads occur before block delivery, never in an audio callback. Playback uses a bounded prefetch plan and substitutes reported silence for missing media rather than blocking the real-time thread.

Recording uses a crash-recoverable partial WAV followed by atomic finalization. Core requires an explicit input acknowledgement, but actual ALSA/CoreAudio/WASAPI capture authority remains with the authenticated platform adapter. A prepared take alone never arms input or output hardware.
