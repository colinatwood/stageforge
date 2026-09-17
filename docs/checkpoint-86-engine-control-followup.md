# Checkpoint 86 engine control/native audio follow-up

This checkpoint adds hosted-safe coverage for the bounded stdin readiness helper and exposes a small runtime-state query used by the recovered engine command integration.

The stdin smoke deliberately accepts ready, timeout, closed, or failed because hosted runners differ in how stdin is attached. Its contract is bounded execution without consuming command bytes.

`EngineNativeAudioRuntime::playback_running()` and `capture_running()` report only the native stream's current execution state. They do not imply endpoint qualification, physical audio quality, automatic endpoint fallback, or automatic rearm.

Safety boundary remains unchanged: `physicalOutputsArmed=false`. Physical Windows/macOS endpoint qualification still requires external hardware evidence.
