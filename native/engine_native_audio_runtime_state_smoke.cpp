#include "engine_native_audio_runtime.h"

int main() {
    stageforge::EngineNativeAudioRuntime runtime;
    if (runtime.playback_running(stageforge::EngineNativeAudioRuntime::kPlaybackSlots)) return 1;
    if (runtime.capture_running(stageforge::EngineNativeAudioRuntime::kCaptureSlots)) return 2;
    runtime.close();
    return 0;
}
