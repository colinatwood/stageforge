#include "engine_native_audio_runtime.h"

#include <iostream>
#include <string>

namespace {
std::string sha(char value) { return "sha256:" + std::string(64, value); }
std::string token() {
    return "native=" + sha('a') + ";persistent=" + sha('b') +
           ";strength=os-stable-endpoint;auto=1";
}
void playback(void*, float*, std::uint32_t, std::uint32_t) noexcept {}
void capture(void*, const float*, std::uint32_t, std::uint32_t) noexcept {}
}

int main() {
    stageforge::EngineNativeAudioRuntime runtime;

    // These cases must fail before touching a real endpoint, making them safe on
    // hosted CI machines with zero target-OS audio endpoints.
    if (runtime.activate_playback(99, token(), 48000.0, 256, 2, "FLOAT_LE", 0, playback, nullptr)) return 1;
    if (runtime.last_error() != "invalid native playback slot") return 2;
    if (runtime.activate_capture(99, token(), 48000.0, 256, 2, "FLOAT_LE", 0, capture, nullptr)) return 3;
    if (runtime.last_error() != "invalid native capture slot") return 4;
    if (runtime.activate_playback(0, "raw-device-id", 48000.0, 256, 2, "FLOAT_LE", 0, playback, nullptr)) return 5;
    if (runtime.activate_capture(0, token(), 48000.0, 256, 2, "S16_LE", 4, capture, nullptr)) return 6;
    if (runtime.activate_playback(0, token(), 48000.0, 256, 2, "FLOAT_LE", 1, playback, nullptr)) return 7;

    runtime.close();
    std::cout << "engine native audio runtime smoke passed\n";
    return 0;
}
