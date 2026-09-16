# Core 5.2.1 generation-fenced punch and loop capture

Core 5.2.1 turns prepared DAW punch metadata into an operational capture gate. After explicit physical-input acknowledgement, the native queue assigns a new arm generation. Every callback block is stamped with that generation; queued residue and late blocks from any prior arm are rejected and counted rather than leaking into the next take.

The background drainer selects the bounded interval beginning at `punchInFrame - preRollFrames`, applies declared input latency compensation, and optionally divides capture into exact loop passes. Pre-roll and compensation are each capped at 65,536 frames and loop capture at 128 passes. When the final punch boundary is observed, input is disarmed automatically. Sequence discontinuities remain dropout evidence and completion atomically publishes the 32-bit WAV.

## Frame-domain boundary

Native input callbacks currently number blocks in the capture adapter's frame domain. Those positions are canonical Show Time only when the adapter is operating at 192 kHz or has converted its clock and audio into that domain. This release exposes `frameDomain: capture-adapter` rather than overstating cross-rate synchronization. Phase-continuous asynchronous resampling and explicit device-clock calibration remain required for arbitrary-rate hardware.

## Safety and qualification

Preparing a plan does not arm anything. Capture start requires acknowledgement, punch completion and abort disarm input, and no capture operation can arm a physical output. Software regressions validate selection, fences and lifecycle behavior; they are not hardware latency, clock, RF or converter qualification.

The provider-neutral extension is `org.upp.daw.punch-loop-capture/1` in public C ABI 1.59. Engine handshake 4.4 advertises `dawPunchLoopCapture=1`.
