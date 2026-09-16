# Core 4.9 capture, delay compensation and mix surface

Core 4.9 closes the software recording path from a native real-time capture callback to a durable DAW take. The callback writes fixed 256-frame blocks into one of eight bounded queues. An authenticated background drainer removes those blocks, preserves their sequence and show-frame positions, converts canonical float32 samples to signed 32-bit PCM and atomically publishes a 192 kHz WAV. Queue gaps become explicit dropout evidence. Recording requires physical-input acknowledgement; it never arms an output.

The capture HTTP surface is `GET /api/v1/daw/capture` and `POST /api/v1/daw/capture` with `start`, `finish` or `abort`. Start accepts `track` from 0 through 7, `takeId`, `fileName` and `acknowledgePhysicalInput: true`. Input-device activation remains a separate operation so selecting a take cannot silently open hardware.

Parallel effect paths can now be planned with `POST /api/v1/daw/plugin-delay-plan`. Each path declares `pathId` and `latencyFrames`; the result assigns the difference from the maximum path latency as `compensationFrames`. The native `PluginDelayCompensator` provides fixed-memory stereo delay lines for real-time use. Plans are limited to 64 paths and 65,536 frames of compensation and fail closed outside those bounds.

The live native engine now owns a double-buffered delay graph for its four output slots. A prepared generation is activated at a callback boundary, and each slot is processed after its effect chain. Status reports the active/prepared generation, processed frames, `audioGraphConnected: true` and `pathBinding: output-slot-index`; live alignment is verified only after an active generation has processed audio. Runtime preparation accepts at most four paths, orders explicit `outputSlot` values and rejects gaps or duplicates.

The browser arrangement view now persists track gain, pan, mute and solo settings through the portable DAW session. Timeline zoom spans 5–300 seconds. Selecting a WAV clip requests bounded peak inspection and renders the first-channel min/max envelope without rewriting source media.

## Safety and qualification boundary

- Capture and delay planning report `physicalOutputsArmed: false`.
- Delay preparation does not activate hardware or change output authority.
- Physical input activation and physical output activation remain separately acknowledged operations.
- Atomic take completion prevents a partial spool from being mistaken for a completed recording.
- Hardware-specific end-to-end latency and multichannel capture still require qualification on the intended audio interface, driver and host.
