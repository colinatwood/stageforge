# Core 5.3 Core-authoritative stage launcher

Core 5.3 adds a performance-facing projection without creating another execution authority. The launcher reads transport, sampler preload, capture/dropout and native MIDI telemetry from Core. Its actions return the same projection, so touch, keyboard and MIDI surfaces converge on one observable state.

The launcher provides large Play/Pause and Stop controls plus at most eight sample pads. Keyboard users have Space, Escape and keys 1–8; focus inside an input, select or text area suppresses global shortcuts. Every pad has an accessible name and readiness state. Layout contracts from four columns to two on narrow screens and avoids precision gestures.

Only verified native sampler preloads become pads. A trigger is submitted to the native sampler's typed Show Event path with the current Show-Time position. Each launcher request carries an action ID retained in a bounded 256-entry replay window, preventing a network retry from double-toggling transport or double-triggering a voice.

The projection reports `authority: core` and `physicalOutputsArmed: false`. It cannot activate an audio endpoint, arm capture or bypass primary/witness authority checks. Physical input and output controls retain their existing explicit acknowledgement boundaries.

The provider-neutral extension is `org.upp.stage.launcher-projection/1` in public C ABI 1.60. This is a client projection, so the native engine remains handshake 4.4.
