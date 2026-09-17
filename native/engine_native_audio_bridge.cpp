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
    try { monitor_.start(); monitor_started_ = true; last_error_.clear(); return true; }
    catch (const std::exception& e) { last_error_ = e.what(); }
    catch (...) { last_error_ = "native device monitor start failed"; }
    return false;
}

bool EngineNativeAudioBridge::ensure_monitor() { return monitor_started_ || start_monitor(); }

void EngineNativeAudioBridge::stop_monitor() {
    for (std::size_t slot = 0; slot < kPlaybackSlots; ++slot) close_playback(slot);
    for (std::size_t slot = 0; slot < kCaptureSlots; ++slot) close_capture(slot);
    if (monitor_started_) monitor_.stop();
    monitor_started_ = false;
}

DeviceSnapshot EngineNativeAudioBridge::snapshot() const { return monitor_started_ ? monitor_.snapshot() : DeviceSnapshot{}; }
std::vector<DeviceRecord> EngineNativeAudioBridge::devices() const { return snapshot().devices; }

bool EngineNativeAudioBridge::activate_playback(std::size_t slot, const DeviceSelection& selection,
                                                const AudioRequest& request, PlaybackRender render, void* context) {
    if (slot >= kPlaybackSlots) { last_error_ = "invalid native playback slot"; return false; }
    close_playback(slot);
    if (!ensure_monitor()) return false;
    if (request.direction != AudioDirection::Playback) { last_error_ = "playback activation received capture request"; return false; }
    try {
        auto fence = std::make_unique<DeviceExecutionFence>(selection);
        if (!fence->arm_initial(devices())) { last_error_ = "selected playback endpoint is not exactly attached and armable"; return false; }
        auto stream = std::make_unique<NativePlaybackStream>(render, context);
        if (!stream->prepare(request, *fence) || !stream->start(*fence)) {
            stream->close(); fence->disarm(); last_error_ = "native playback prepare/start rejected selected endpoint"; return false;
        }
        playback_fences_[slot] = std::move(fence); playbacks_[slot] = std::move(stream); last_error_.clear(); return true;
    } catch (const std::exception& e) { last_error_ = e.what(); }
    catch (...) { last_error_ = "native playback activation failed"; }
    close_playback(slot); return false;
}

bool EngineNativeAudioBridge::activate_capture(std::size_t slot, const DeviceSelection& selection,
                                               const AudioRequest& request, CaptureReceive receive, void* context) {
    if (slot >= kCaptureSlots) { last_error_ = "invalid native capture slot"; return false; }
    close_capture(slot);
    if (!ensure_monitor()) return false;
    if (request.direction != AudioDirection::Capture) { last_error_ = "capture activation received playback request"; return false; }
    try {
        auto fence = std::make_unique<DeviceExecutionFence>(selection);
        if (!fence->arm_initial(devices())) { last_error_ = "selected capture endpoint is not exactly attached and armable"; return false; }
        auto stream = std::make_unique<NativeCaptureStream>(receive, context);
        if (!stream->prepare(request, *fence) || !stream->start(*fence)) {
            stream->close(); fence->disarm(); last_error_ = "native capture prepare/start rejected selected endpoint"; return false;
        }
        capture_fences_[slot] = std::move(fence); captures_[slot] = std::move(stream); last_error_.clear(); return true;
    } catch (const std::exception& e) { last_error_ = e.what(); }
    catch (...) { last_error_ = "native capture activation failed"; }
    close_capture(slot); return false;
}

void EngineNativeAudioBridge::service(std::uint32_t wait_ms) {
    for (std::size_t slot = 0; slot < kPlaybackSlots; ++slot)
        if (playbacks_[slot] && playback_fences_[slot]) playbacks_[slot]->service(*playback_fences_[slot], wait_ms);
    for (std::size_t slot = 0; slot < kCaptureSlots; ++slot)
        if (captures_[slot] && capture_fences_[slot]) captures_[slot]->service(*capture_fences_[slot], wait_ms);
}

void EngineNativeAudioBridge::close_playback(std::size_t slot) {
    if (slot >= kPlaybackSlots) return;
    if (playbacks_[slot]) playbacks_[slot]->close();
    playbacks_[slot].reset();
    if (playback_fences_[slot]) playback_fences_[slot]->disarm();
    playback_fences_[slot].reset();
}
void EngineNativeAudioBridge::close_capture(std::size_t slot) {
    if (slot >= kCaptureSlots) return;
    if (captures_[slot]) captures_[slot]->close();
    captures_[slot].reset();
    if (capture_fences_[slot]) capture_fences_[slot]->disarm();
    capture_fences_[slot].reset();
}
void EngineNativeAudioBridge::close() { stop_monitor(); }

FenceObservation EngineNativeAudioBridge::reconcile_playback(std::size_t slot) {
    if (slot >= kPlaybackSlots || !playback_fences_[slot]) return {};
    const auto observation = playback_fences_[slot]->reconcile(devices());
    if (playbacks_[slot]) playbacks_[slot]->service(*playback_fences_[slot]);
    return observation;
}
FenceObservation EngineNativeAudioBridge::reconcile_capture(std::size_t slot) {
    if (slot >= kCaptureSlots || !capture_fences_[slot]) return {};
    const auto observation = capture_fences_[slot]->reconcile(devices());
    if (captures_[slot]) captures_[slot]->service(*capture_fences_[slot]);
    return observation;
}
bool EngineNativeAudioBridge::explicit_rearm_playback(std::size_t slot) {
    return slot < kPlaybackSlots && playback_fences_[slot] && playback_fences_[slot]->explicit_rearm(devices());
}
bool EngineNativeAudioBridge::explicit_rearm_capture(std::size_t slot) {
    return slot < kCaptureSlots && capture_fences_[slot] && capture_fences_[slot]->explicit_rearm(devices());
}
EndpointStreamStats EngineNativeAudioBridge::playback_stats(std::size_t slot) const {
    return slot < kPlaybackSlots && playbacks_[slot] ? playbacks_[slot]->stats() : EndpointStreamStats{};
}
EndpointStreamStats EngineNativeAudioBridge::capture_stats(std::size_t slot) const {
    return slot < kCaptureSlots && captures_[slot] ? captures_[slot]->stats() : EndpointStreamStats{};
}

} // namespace stageforge
