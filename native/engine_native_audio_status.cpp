#include "engine_native_audio_status.h"

#include "audio_preflight.h"

namespace stageforge {

EngineNativeAudioStatus project_engine_native_audio_status(
    const EndpointStreamStats& stats) noexcept {
    EngineNativeAudioStatus result{};
    result.running = stats.native_running;
    result.callback_fault = stats.callback_fault;
    result.callbacks = stats.callbacks;
    result.frames = stats.frames;
    result.discontinuities = stats.discontinuities;
    result.sample_rate_hz = stats.last_verified_configuration.configured_sample_rate_hz;
    result.period_frames = stats.last_verified_configuration.configured_period_frames;
    result.channels = stats.last_verified_configuration.configured_channels;
    result.sample_format = audio_sample_format_name(
        stats.last_verified_configuration.configured_format);
    return result;
}

} // namespace stageforge
