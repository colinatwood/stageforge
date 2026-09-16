# Core 4.7 native playback and capture queues

The arrangement playback producer resolves media and fills fixed blocks ahead of the callback. The primary output callback consumes only a block matching its current generation, playhead and frame count. Missing data becomes silence with an underrun count; mismatched data becomes silence with a discontinuity count. Seek stops playback, drops queued blocks and advances generation.

Loop state advances the canonical playhead without changing Show Time. Physical output activation remains a separate authority-controlled operation.

Each capture track has an independent single-producer/single-consumer queue. Input callbacks submit float blocks; writer threads drain them into crash-safe recording spools. Full queues drop the incoming block and record the loss, and non-contiguous writer sequences record a gap. Arming is explicit per track and never arms output hardware.
