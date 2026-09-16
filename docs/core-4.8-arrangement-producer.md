# Core 4.8 arrangement producer and capture bridge

The arrangement producer is a control/background service. It reads project media, performs canonical-rate conversion and arrangement mixing, and submits bounded PCM blocks to the authenticated native engine. The audio callback only consumes the already-prefetched native blocks.

Every producer run first seeks the native queue and captures the new generation. All later blocks carry that generation and exact canonical start frame. Eight blocks are prefetched before playback starts, while the producer caps read-ahead at 24 blocks. Queue pressure delays the producer rather than blocking the callback.

Physical input callbacks now copy capture into their assigned fixed recording queue. File writing remains a consumer-thread responsibility. Overflow and sequence gaps are observable evidence, never silently classified as a clean recording. Playback, recording-track arming and physical output activation remain separate controls.
