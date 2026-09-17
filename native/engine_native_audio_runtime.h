#pragma once

#include "engine_native_audio_bridge.h"
#include "engine_native_audio_callbacks.h"
#include "engine_native_audio_request.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace stageforge {

// Thin full-engine facade around the target-OS bridge. It keeps the recovered
// engine_main command handlers declarative: validate the hash-only selection,
// translate the AUDIO_* request, bind the existing callback ABI, and activate
// the exact selected endpoint. No default endpoint or implicit rearm exists here.
class EngineNativeAudioRuntime {
public:
    static constexpr std::size_t kPlaybackSlots = EngineNativeAudioBridge::kPlaybackSlots;
    static constexpr std::size_t kCaptureSlots = EngineNativeAudioBridge::kCaptureSlots;

    bool activate_playback(std::size_t slot, std::string_view identity_token,
                           double sample_rate, std::uint32_t period_frames,
                           std::uint32_t channels, std::string_view sample_format,
                           std::uint32_t conversion_flags,
                           EnginePlaybackCallback callback, void* context);
    bool activate_capture(std::size_t slot, std::string_view identity_token,
                          double sample_rate, std::uint32_t period_frames,
                          std::uint32_t channels, std::string_view sample_format,
                          std::uint32_t conversion_flags,
                          EngineCaptureCallback callback, void* context);

    void close_playback(std::size_t slot);
    void close_capture(std::size_t slot);
    void close();
    void service(std::uint32_t wait_ms = 0);

    EndpointStreamStats playback_stats(std::size_t slot) const;
    EndpointStreamStats capture_stats(std::size_t slot) const;
    FenceObservation reconcile_playback(std::size_t slot);
    FenceObservation reconcile_capture(std::size_t slot);
    bool explicit_rearm_playback(std::size_t slot);
    bool explicit_rearm_capture(std::size_t slot);

    bool playback_running(std::size_t slot) const noexcept {
        return slot < kPlaybackSlots && playback_stats(slot).native_running;
    }
    bool capture_running(std::size_t slot) const noexcept {
        return slot < kCaptureSlots && capture_stats(slot).native_running;
    }

    const std::string& last_error() const noexcept { return last_error_; }

private:
    EngineNativeAudioBridge bridge_;
    std::array<EngineNativePlaybackCallbackContext, kPlaybackSlots> playback_callbacks_{};
    std::array<EngineNativeCaptureCallbackContext, kCaptureSlots> capture_callbacks_{};
    std::string last_error_;
};

} // namespace stageforge
