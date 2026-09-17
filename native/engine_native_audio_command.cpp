#include "engine_native_audio_command.h"

namespace stageforge {
namespace {

EngineNativeAudioCommandResult from_stats(const EndpointStreamStats& stats) {
    EngineNativeAudioCommandResult result{};
    result.ok = stats.native_running && !stats.callback_fault;
    result.running = stats.native_running;
    result.sample_rate_hz = stats.last_verified_configuration.configured_sample_rate_hz;
    result.period_frames = stats.last_verified_configuration.configured_period_frames;
    result.channels = stats.last_verified_configuration.configured_channels;
    result.sample_format = audio_sample_format_name(stats.last_verified_configuration.configured_format);
    if (stats.callback_fault) result.error = "native audio callback fault";
    else if (!stats.native_running) result.error = "native audio stream is not running";
    return result;
}

} // namespace

EngineNativeAudioCommandResult activate_engine_native_playback(
    EngineNativeAudioRuntime& runtime, std::size_t slot, std::string_view identity_token,
    double sample_rate, std::uint32_t period_frames, std::uint32_t channels,
    std::string_view sample_format, std::uint32_t conversion_flags,
    EnginePlaybackCallback callback, void* context) {
    if (!runtime.activate_playback(slot, identity_token, sample_rate, period_frames, channels,
                                   sample_format, conversion_flags, callback, context)) {
        EngineNativeAudioCommandResult result{};
        result.error = runtime.last_error().empty() ? "unable to start native playback" : runtime.last_error();
        return result;
    }
    auto result = from_stats(runtime.playback_stats(slot));
    if (!result.ok) runtime.close_playback(slot);
    return result;
}

EngineNativeAudioCommandResult activate_engine_native_capture(
    EngineNativeAudioRuntime& runtime, std::size_t slot, std::string_view identity_token,
    double sample_rate, std::uint32_t period_frames, std::uint32_t channels,
    std::string_view sample_format, std::uint32_t conversion_flags,
    EngineCaptureCallback callback, void* context) {
    if (!runtime.activate_capture(slot, identity_token, sample_rate, period_frames, channels,
                                  sample_format, conversion_flags, callback, context)) {
        EngineNativeAudioCommandResult result{};
        result.error = runtime.last_error().empty() ? "unable to start native capture" : runtime.last_error();
        return result;
    }
    auto result = from_stats(runtime.capture_stats(slot));
    if (!result.ok) runtime.close_capture(slot);
    return result;
}

EngineNativeAudioCommandResult engine_native_playback_status(
    const EngineNativeAudioRuntime& runtime, std::size_t slot) {
    if (slot >= EngineNativeAudioRuntime::kPlaybackSlots) {
        EngineNativeAudioCommandResult result{};
        result.error = "invalid native playback slot";
        return result;
    }
    return from_stats(runtime.playback_stats(slot));
}

EngineNativeAudioCommandResult engine_native_capture_status(
    const EngineNativeAudioRuntime& runtime, std::size_t slot) {
    if (slot >= EngineNativeAudioRuntime::kCaptureSlots) {
        EngineNativeAudioCommandResult result{};
        result.error = "invalid native capture slot";
        return result;
    }
    return from_stats(runtime.capture_stats(slot));
}

} // namespace stageforge
