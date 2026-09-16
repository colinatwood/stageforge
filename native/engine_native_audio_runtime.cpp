#include "engine_native_audio_runtime.h"

namespace stageforge {

bool EngineNativeAudioRuntime::activate_playback(std::size_t slot, std::string_view identity_token,
                                                 double sample_rate, std::uint32_t period_frames,
                                                 std::uint32_t channels, std::string_view sample_format,
                                                 std::uint32_t conversion_flags,
                                                 EnginePlaybackCallback callback, void* context) {
    if (slot >= kPlaybackSlots) { last_error_ = "invalid native playback slot"; return false; }
    DeviceSelection selection{};
    AudioRequest request{};
    if (!EngineNativeAudioBridge::decode_selection(identity_token, false, true, selection)) {
        last_error_ = "invalid hash-only native playback selection"; return false;
    }
    if (!make_engine_native_audio_request(AudioDirection::Playback, sample_rate, period_frames,
                                          channels, sample_format, conversion_flags, request)) {
        last_error_ = "native playback request requires exact float32 endpoint configuration"; return false;
    }
    playback_callbacks_[slot] = {callback, context};
    if (!bridge_.activate_playback(slot, selection, request, engine_native_playback_callback,
                                   &playback_callbacks_[slot])) {
        playback_callbacks_[slot] = {};
        last_error_ = bridge_.last_error();
        return false;
    }
    last_error_.clear();
    return true;
}

bool EngineNativeAudioRuntime::activate_capture(std::size_t slot, std::string_view identity_token,
                                                double sample_rate, std::uint32_t period_frames,
                                                std::uint32_t channels, std::string_view sample_format,
                                                std::uint32_t conversion_flags,
                                                EngineCaptureCallback callback, void* context) {
    if (slot >= kCaptureSlots) { last_error_ = "invalid native capture slot"; return false; }
    DeviceSelection selection{};
    AudioRequest request{};
    if (!EngineNativeAudioBridge::decode_selection(identity_token, true, false, selection)) {
        last_error_ = "invalid hash-only native capture selection"; return false;
    }
    if (!make_engine_native_audio_request(AudioDirection::Capture, sample_rate, period_frames,
                                          channels, sample_format, conversion_flags, request)) {
        last_error_ = "native capture request requires exact float32 endpoint configuration"; return false;
    }
    capture_callbacks_[slot] = {callback, context};
    if (!bridge_.activate_capture(slot, selection, request, engine_native_capture_callback,
                                  &capture_callbacks_[slot])) {
        capture_callbacks_[slot] = {};
        last_error_ = bridge_.last_error();
        return false;
    }
    last_error_.clear();
    return true;
}

void EngineNativeAudioRuntime::close_playback(std::size_t slot) {
    bridge_.close_playback(slot);
    if (slot < kPlaybackSlots) playback_callbacks_[slot] = {};
}
void EngineNativeAudioRuntime::close_capture(std::size_t slot) {
    bridge_.close_capture(slot);
    if (slot < kCaptureSlots) capture_callbacks_[slot] = {};
}
void EngineNativeAudioRuntime::close() {
    bridge_.close();
    playback_callbacks_.fill({});
    capture_callbacks_.fill({});
}
void EngineNativeAudioRuntime::service(std::uint32_t wait_ms) { bridge_.service(wait_ms); }
EndpointStreamStats EngineNativeAudioRuntime::playback_stats(std::size_t slot) const { return bridge_.playback_stats(slot); }
EndpointStreamStats EngineNativeAudioRuntime::capture_stats(std::size_t slot) const { return bridge_.capture_stats(slot); }
FenceObservation EngineNativeAudioRuntime::reconcile_playback(std::size_t slot) { return bridge_.reconcile_playback(slot); }
FenceObservation EngineNativeAudioRuntime::reconcile_capture(std::size_t slot) { return bridge_.reconcile_capture(slot); }
bool EngineNativeAudioRuntime::explicit_rearm_playback(std::size_t slot) { return bridge_.explicit_rearm_playback(slot); }
bool EngineNativeAudioRuntime::explicit_rearm_capture(std::size_t slot) { return bridge_.explicit_rearm_capture(slot); }

} // namespace stageforge
