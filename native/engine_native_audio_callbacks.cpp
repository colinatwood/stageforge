#include "engine_native_audio_callbacks.h"

#include <algorithm>
#include <cstddef>

namespace stageforge {

void engine_native_playback_callback(float* interleaved, std::uint32_t frames,
                                     std::uint32_t channels, void* raw) noexcept {
    auto* adapter = static_cast<EngineNativePlaybackCallbackContext*>(raw);
    if (!adapter || !adapter->callback) {
        if (interleaved && frames && channels) {
            std::fill_n(interleaved, static_cast<std::size_t>(frames) * channels, 0.0F);
        }
        return;
    }
    adapter->callback(adapter->context, interleaved, frames, channels);
}

void engine_native_capture_callback(const float* interleaved, std::uint32_t frames,
                                    std::uint32_t channels, const CapturePacketInfo&,
                                    void* raw) noexcept {
    auto* adapter = static_cast<EngineNativeCaptureCallbackContext*>(raw);
    if (!adapter || !adapter->callback || !interleaved || frames == 0 || channels == 0) return;
    adapter->callback(adapter->context, interleaved, frames, channels);
}

} // namespace stageforge
