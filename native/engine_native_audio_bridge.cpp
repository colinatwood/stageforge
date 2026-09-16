#include "engine_native_audio_bridge.h"

#include <exception>

namespace stageforge {

EngineNativeAudioBridge::EngineNativeAudioBridge() = default;
EngineNativeAudioBridge::~EngineNativeAudioBridge() { close(); }

bool EngineNativeAudioBridge::start_monitor() {
    if (monitor_started_) return true;
    try {
        monitor_.start();
        monitor_started_ = true;
        last_error_.clear();
        return true;
    } catch (const std::exception& e) {
        last_error_ = e.what();
    } catch (...) {
        last_error_ = "native device monitor start failed";
    }
    return false;
}

bool EngineNativeAudioBridge::ensure_monitor() { return monitor_started_ || start_monitor(); }

void EngineNativeAudioBridge::stop_monitor() {
    close_playback();
    close_capture();
    if (monitor_started_) monitor_.stop();
    monitor_started_ = false;
}

DeviceSnapshot EngineNativeAudioBridge::snapshot() const {
    if (!monitor_started_) return {};
    return monitor_.snapshot();
}

std::vector<DeviceRecord> EngineNativeAudioBridge::devices() const {
    return snapshot().devices;
}

bool EngineNativeAudioBridge::activate_playback(const DeviceSelection& selection,
                                                const AudioRequest& request,
                                                PlaybackRender render, void* context) {
    close_playback();
    if (!ensure_monitor()) return false;
    if (request.direction != AudioDirection::Playback) {
        last_error_ = "playback activation received capture request";
        return false;
    }
    try {
        auto fence = std::make_unique<DeviceExecutionFence>(selection);
        const auto current = devices();
        if (!fence->arm_initial(current)) {
            last_error_ = "selected playback endpoint is not exactly attached and armable";
            return false;
        }
        auto stream = std::make_unique<NativePlaybackStream>(render, context);
        if (!stream->prepare(request, *fence) || !stream->start(*fence)) {
            stream->close();
            fence->disarm();
            last_error_ = "native playback prepare/start rejected selected endpoint";
            return false;
        }
        playback_fence_ = std::move(fence);
        playback_ = std::move(stream);
        last_error_.clear();
        return true;
    } catch (const std::exception& e) {
        last_error_ = e.what();
    } catch (...) {
        last_error_ = "native playback activation failed";
    }
    close_playback();
    return false;
}

bool EngineNativeAudioBridge::activate_capture(const DeviceSelection& selection,
                                               const AudioRequest& request,
                                               CaptureReceive receive, void* context) {
    close_capture();
    if (!ensure_monitor()) return false;
    if (request.direction != AudioDirection::Capture) {
        last_error_ = "capture activation received playback request";
        return false;
    }
    try {
        auto fence = std::make_unique<DeviceExecutionFence>(selection);
        const auto current = devices();
        if (!fence->arm_initial(current)) {
            last_error_ = "selected capture endpoint is not exactly attached and armable";
            return false;
        }
        auto stream = std::make_unique<NativeCaptureStream>(receive, context);
        if (!stream->prepare(request, *fence) || !stream->start(*fence)) {
            stream->close();
            fence->disarm();
            last_error_ = "native capture prepare/start rejected selected endpoint";
            return false;
        }
        capture_fence_ = std::move(fence);
        capture_ = std::move(stream);
        last_error_.clear();
        return true;
    } catch (const std::exception& e) {
        last_error_ = e.what();
    } catch (...) {
        last_error_ = "native capture activation failed";
    }
    close_capture();
    return false;
}

void EngineNativeAudioBridge::service(std::uint32_t wait_ms) {
    if (playback_ && playback_fence_) playback_->service(*playback_fence_, wait_ms);
    if (capture_ && capture_fence_) capture_->service(*capture_fence_, wait_ms);
}

void EngineNativeAudioBridge::close_playback() {
    if (playback_) playback_->close();
    playback_.reset();
    if (playback_fence_) playback_fence_->disarm();
    playback_fence_.reset();
}

void EngineNativeAudioBridge::close_capture() {
    if (capture_) capture_->close();
    capture_.reset();
    if (capture_fence_) capture_fence_->disarm();
    capture_fence_.reset();
}

void EngineNativeAudioBridge::close() { stop_monitor(); }

FenceObservation EngineNativeAudioBridge::reconcile_playback() {
    if (!playback_fence_) return {};
    const auto observation = playback_fence_->reconcile(devices());
    if (playback_) playback_->service(*playback_fence_);
    return observation;
}

FenceObservation EngineNativeAudioBridge::reconcile_capture() {
    if (!capture_fence_) return {};
    const auto observation = capture_fence_->reconcile(devices());
    if (capture_) capture_->service(*capture_fence_);
    return observation;
}

bool EngineNativeAudioBridge::explicit_rearm_playback() {
    return playback_fence_ && playback_fence_->explicit_rearm(devices());
}

bool EngineNativeAudioBridge::explicit_rearm_capture() {
    return capture_fence_ && capture_fence_->explicit_rearm(devices());
}

EndpointStreamStats EngineNativeAudioBridge::playback_stats() const {
    return playback_ ? playback_->stats() : EndpointStreamStats{};
}

EndpointStreamStats EngineNativeAudioBridge::capture_stats() const {
    return capture_ ? capture_->stats() : EndpointStreamStats{};
}

} // namespace stageforge
