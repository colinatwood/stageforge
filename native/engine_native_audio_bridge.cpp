#include "engine_native_audio_bridge.h"

#include <exception>

namespace stageforge {
namespace {

bool valid_sha256_token(std::string_view value) noexcept {
    if (value.size() != 71 || value.substr(0, 7) != "sha256:") return false;
    for (const char ch : value.substr(7)) {
        const bool digit = ch >= '0' && ch <= '9';
        const bool lower = ch >= 'a' && ch <= 'f';
        if (!digit && !lower) return false;
    }
    return true;
}

bool take_field(std::string_view token, std::string_view key, std::string_view& value) noexcept {
    const auto begin = token.find(key);
    if (begin == std::string_view::npos || (begin != 0 && token[begin - 1] != ';')) return false;
    const auto first = begin + key.size();
    const auto end = token.find(';', first);
    value = token.substr(first, end == std::string_view::npos ? token.size() - first : end - first);
    return !value.empty();
}

} // namespace

EngineNativeAudioBridge::EngineNativeAudioBridge() = default;
EngineNativeAudioBridge::~EngineNativeAudioBridge() { close(); }

bool EngineNativeAudioBridge::decode_selection(std::string_view token, bool require_input,
                                               bool require_output, DeviceSelection& selection) {
    std::string_view native_hash, persistent_hash, strength, automatic;
    if (!take_field(token, "native=", native_hash) ||
        !take_field(token, "persistent=", persistent_hash) ||
        !take_field(token, "strength=", strength) ||
        !take_field(token, "auto=", automatic) ||
        !valid_sha256_token(native_hash) || !valid_sha256_token(persistent_hash) ||
        (automatic != "0" && automatic != "1")) return false;

    // Only OS-stable identity may carry automatic reconnect authority. The
    // installation/volatile cases remain exact-native-only and never acquire it
    // merely because a caller supplied auto=1 in a forged legacy address token.
    const bool strong = strength == "os-stable-endpoint";
    if (!strong && strength != "installation-snapshot" && strength != "volatile") return false;
    if (!strong && automatic == "1") return false;

    selection = {};
    selection.kind = DeviceKind::Audio;
    selection.native_hash.assign(native_hash);
    selection.persistent_hash.assign(persistent_hash);
    selection.automatic_reconnect = strong && automatic == "1";
    selection.require_input = require_input;
    selection.require_output = require_output;
    return true;
}

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
