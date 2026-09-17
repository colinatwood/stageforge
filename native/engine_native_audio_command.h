#pragma once

#include "engine_native_audio_runtime.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace stageforge {

struct EngineNativeAudioCommandResult {
    bool ok{false};
    bool running{false};
    std::uint32_t sample_rate_hz{0};
    std::uint32_t period_frames{0};
    std::uint32_t channels{0};
    std::string sample_format{"unknown"};
    std::string error;
};

EngineNativeAudioCommandResult activate_engine_native_playback(
    EngineNativeAudioRuntime& runtime, std::size_t slot, std::string_view identity_token,
    double sample_rate, std::uint32_t period_frames, std::uint32_t channels,
    std::string_view sample_format, std::uint32_t conversion_flags,
    EnginePlaybackCallback callback, void* context);

EngineNativeAudioCommandResult activate_engine_native_capture(
    EngineNativeAudioRuntime& runtime, std::size_t slot, std::string_view identity_token,
    double sample_rate, std::uint32_t period_frames, std::uint32_t channels,
    std::string_view sample_format, std::uint32_t conversion_flags,
    EngineCaptureCallback callback, void* context);

EngineNativeAudioCommandResult engine_native_playback_status(
    const EngineNativeAudioRuntime& runtime, std::size_t slot);
EngineNativeAudioCommandResult engine_native_capture_status(
    const EngineNativeAudioRuntime& runtime, std::size_t slot);

} // namespace stageforge
