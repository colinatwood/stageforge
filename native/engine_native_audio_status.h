#pragma once

#include "native_endpoint_stream.h"

#include <cstdint>

namespace stageforge {

// Engine-facing status projection for native endpoint streams. Native endpoint
// discontinuities are intentionally separate from ALSA xruns.
struct EngineNativeAudioStatus {
    bool running = false;
    bool callback_fault = false;
    std::uint64_t callbacks = 0;
    std::uint64_t frames = 0;
    std::uint64_t discontinuities = 0;
    std::uint32_t sample_rate_hz = 0;
    std::uint32_t period_frames = 0;
    std::uint32_t channels = 0;
    const char* sample_format = "FLOAT_LE";
};

EngineNativeAudioStatus project_engine_native_audio_status(
    const EndpointStreamStats& stats) noexcept;

} // namespace stageforge
