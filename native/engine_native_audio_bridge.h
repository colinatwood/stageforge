#pragma once

#include "device_execution_fence.h"
#include "device_monitor.h"
#include "native_capture.h"
#include "native_playback.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

namespace stageforge {

// Control-thread owner used by the recovered engine to bind its render/capture
// callbacks to the already-qualified target-OS endpoint streams. The bridge owns
// one process-lifetime monitor and never substitutes a default endpoint.
class EngineNativeAudioBridge {
public:
    static constexpr std::size_t kPlaybackSlots = 4;
    static constexpr std::size_t kCaptureSlots = 4;

    EngineNativeAudioBridge();
    ~EngineNativeAudioBridge();
    EngineNativeAudioBridge(const EngineNativeAudioBridge&) = delete;
    EngineNativeAudioBridge& operator=(const EngineNativeAudioBridge&) = delete;

    // Decode the hash-only identity token exported by AudioDeviceManager. Raw OS
    // identifiers are never accepted here. Direction requirements are pinned into
    // the resulting selection so a playback/capture mismatch fails closed.
    static bool decode_selection(std::string_view token, bool require_input,
                                 bool require_output, DeviceSelection& selection);

    bool start_monitor();
    void stop_monitor();
    DeviceSnapshot snapshot() const;

    bool activate_playback(std::size_t slot, const DeviceSelection& selection, const AudioRequest& request,
                           PlaybackRender render, void* context);
    bool activate_capture(std::size_t slot, const DeviceSelection& selection, const AudioRequest& request,
                          CaptureReceive receive, void* context);
    void service(std::uint32_t wait_ms = 0);
    void close_playback(std::size_t slot);
    void close_capture(std::size_t slot);
    void close();

    // Recovery is deliberately two-stage: reconcile never restarts I/O. The
    // caller must issue explicit_rearm_* and then activate again.
    FenceObservation reconcile_playback(std::size_t slot);
    FenceObservation reconcile_capture(std::size_t slot);
    bool explicit_rearm_playback(std::size_t slot);
    bool explicit_rearm_capture(std::size_t slot);

    EndpointStreamStats playback_stats(std::size_t slot) const;
    EndpointStreamStats capture_stats(std::size_t slot) const;
    const std::string& last_error() const noexcept { return last_error_; }

private:
    bool ensure_monitor();
    std::vector<DeviceRecord> devices() const;

    DeviceMonitor monitor_;
    bool monitor_started_{false};
    std::array<std::unique_ptr<DeviceExecutionFence>, kPlaybackSlots> playback_fences_{};
    std::array<std::unique_ptr<DeviceExecutionFence>, kCaptureSlots> capture_fences_{};
    std::array<std::unique_ptr<NativePlaybackStream>, kPlaybackSlots> playbacks_{};
    std::array<std::unique_ptr<NativeCaptureStream>, kCaptureSlots> captures_{};
    std::string last_error_;
};

} // namespace stageforge
