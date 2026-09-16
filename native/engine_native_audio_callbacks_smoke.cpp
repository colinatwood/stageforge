#include "engine_native_audio_callbacks.h"

#include <array>
#include <cstdint>
#include <iostream>

namespace {

struct PlaybackState { std::uint64_t calls = 0; };
struct CaptureState { std::uint64_t calls = 0; float first = 0.0F; };

void render(void* raw, float* samples, std::uint32_t frames, std::uint32_t channels) noexcept {
    auto* state = static_cast<PlaybackState*>(raw);
    ++state->calls;
    for (std::uint32_t i = 0; i < frames * channels; ++i) samples[i] = 0.25F;
}

void capture(void* raw, const float* samples, std::uint32_t, std::uint32_t) noexcept {
    auto* state = static_cast<CaptureState*>(raw);
    ++state->calls;
    state->first = samples[0];
}

} // namespace

int main() {
    std::array<float, 8> playback{};
    PlaybackState playback_state{};
    stageforge::EngineNativePlaybackCallbackContext playback_context{&render, &playback_state};
    stageforge::engine_native_playback_callback(playback.data(), 4, 2, &playback_context);
    if (playback_state.calls != 1 || playback[0] != 0.25F || playback[7] != 0.25F) return 1;

    playback.fill(1.0F);
    stageforge::engine_native_playback_callback(playback.data(), 4, 2, nullptr);
    for (float sample : playback) if (sample != 0.0F) return 2;

    const std::array<float, 4> captured{0.5F, -0.5F, 0.25F, -0.25F};
    CaptureState capture_state{};
    stageforge::EngineNativeCaptureCallbackContext capture_context{&capture, &capture_state};
    stageforge::CapturePacketInfo packet{};
    stageforge::engine_native_capture_callback(captured.data(), 2, 2, packet, &capture_context);
    if (capture_state.calls != 1 || capture_state.first != 0.5F) return 3;

    stageforge::engine_native_capture_callback(nullptr, 2, 2, packet, &capture_context);
    if (capture_state.calls != 1) return 4;

    std::cout << "engine native audio callback adapter smoke passed\n";
    return 0;
}
