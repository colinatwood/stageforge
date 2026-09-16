#include "engine_native_audio_request.h"

#include <cmath>
#include <limits>

namespace stageforge {

bool make_engine_native_audio_request(AudioDirection direction,
                                      double sample_rate,
                                      std::uint32_t period_frames,
                                      std::uint32_t channels,
                                      std::string_view sample_format,
                                      std::uint32_t conversion_flags,
                                      AudioRequest& request) noexcept {
    if (!std::isfinite(sample_rate) || sample_rate < 8000.0 || sample_rate > 384000.0 ||
        sample_rate > static_cast<double>(std::numeric_limits<std::uint32_t>::max()) ||
        period_frames < 16 || period_frames > 8192 || channels < 1 || channels > 32 ||
        conversion_flags > 7U) {
        return false;
    }

    // NativeEndpointStream currently exposes only interleaved float32 callbacks.
    // Permission to convert in the recovered engine is not evidence that the
    // endpoint adapter implements an integer client format, so reject it here.
    if (sample_format != "FLOAT_LE") return false;

    AudioRequest candidate{};
    candidate.direction = direction;
    candidate.sample_rate_hz = static_cast<std::uint32_t>(std::llround(sample_rate));
    candidate.period_frames = period_frames;
    candidate.channels = channels;
    candidate.format = AudioSampleFormat::Float32;

    // The request describes the exact host configuration to open. The engine's
    // canonical render/capture path may convert around that configuration, but
    // native preflight must not silently adapt the selected endpoint itself.
    candidate.allow_rate_conversion = false;
    candidate.allow_period_adaptation = false;
    candidate.allow_channel_conversion = false;
    candidate.allow_format_conversion = false;

    request = candidate;
    return true;
}

} // namespace stageforge
