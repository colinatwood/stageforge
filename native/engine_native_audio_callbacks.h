#pragma once

#include "native_endpoint_stream.h"

#include <cstdint>

namespace stageforge {

// Adapter boundary between the recovered engine callback ABI and the qualified
// target-OS endpoint stream ABI. The endpoint owns only the borrowed buffer for
// the duration of each call; these adapters never retain it.
using EnginePlaybackCallback = void (*)(void*, float*, std::uint32_t, std::uint32_t) noexcept;
using EngineCaptureCallback = void (*)(void*, const float*, std::uint32_t, std::uint32_t) noexcept;

struct EngineNativePlaybackCallbackContext {
    EnginePlaybackCallback callback = nullptr;
    void* context = nullptr;
};

struct EngineNativeCaptureCallbackContext {
    EngineCaptureCallback callback = nullptr;
    void* context = nullptr;
};

void engine_native_playback_callback(float* interleaved, std::uint32_t frames,
                                     std::uint32_t channels, void* raw) noexcept;
void engine_native_capture_callback(const float* interleaved, std::uint32_t frames,
                                    std::uint32_t channels, const CapturePacketInfo& packet,
                                    void* raw) noexcept;

} // namespace stageforge
