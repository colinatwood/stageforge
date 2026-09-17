#include "engine_native_audio_status.h"

#include <cassert>
#include <string_view>

int main() {
    stageforge::EndpointStreamStats stats{};
    stats.callbacks = 17;
    stats.frames = 4352;
    stats.native_running = true;
    stats.callback_fault = false;
    stats.discontinuities = 3;
    stats.last_verified_configuration.configured_sample_rate_hz = 48000;
    stats.last_verified_configuration.configured_period_frames = 256;
    stats.last_verified_configuration.configured_channels = 2;
    stats.last_verified_configuration.configured_format = stageforge::AudioSampleFormat::Float32;

    const auto projected = stageforge::project_engine_native_audio_status(stats);
    assert(projected.running);
    assert(!projected.callback_fault);
    assert(projected.callbacks == 17);
    assert(projected.frames == 4352);
    assert(projected.discontinuities == 3);
    assert(projected.sample_rate_hz == 48000);
    assert(projected.period_frames == 256);
    assert(projected.channels == 2);
    assert(std::string_view(projected.sample_format) == "float32");

    // Native discontinuities remain their own counter. The projection has no
    // xrun field, preventing accidental relabeling as ALSA xruns.
    stats.native_running = false;
    stats.callback_fault = true;
    const auto stopped = stageforge::project_engine_native_audio_status(stats);
    assert(!stopped.running);
    assert(stopped.callback_fault);
    assert(stopped.discontinuities == 3);
    return 0;
}
