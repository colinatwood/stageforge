#include "engine_native_audio_command.h"

#include <cassert>

int main() {
    stageforge::EngineNativeAudioRuntime runtime;

    const auto playback = stageforge::engine_native_playback_status(
        runtime, stageforge::EngineNativeAudioRuntime::kPlaybackSlots);
    assert(!playback.ok);
    assert(!playback.running);
    assert(playback.error == "invalid native playback slot");

    const auto capture = stageforge::engine_native_capture_status(
        runtime, stageforge::EngineNativeAudioRuntime::kCaptureSlots);
    assert(!capture.ok);
    assert(!capture.running);
    assert(capture.error == "invalid native capture slot");

    const auto activation = stageforge::activate_engine_native_playback(
        runtime, stageforge::EngineNativeAudioRuntime::kPlaybackSlots,
        "native=sha256:0000000000000000000000000000000000000000000000000000000000000000;"
        "persistent=sha256:0000000000000000000000000000000000000000000000000000000000000000;"
        "strength=os-stable-endpoint;auto=1",
        48000.0, 256, 2, "FLOAT_LE", 0, nullptr, nullptr);
    assert(!activation.ok);
    assert(!activation.running);
    assert(!activation.error.empty());

    runtime.close();
    return 0;
}
