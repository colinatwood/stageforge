#include "engine_native_audio_request.h"

#include <iostream>

int main() {
    stageforge::AudioRequest request{};
    if (!stageforge::make_engine_native_audio_request(stageforge::AudioDirection::Playback,
            48000.0, 256, 2, "FLOAT_LE", 0, request)) return 1;
    if (request.direction != stageforge::AudioDirection::Playback || request.sample_rate_hz != 48000 ||
        request.period_frames != 256 || request.channels != 2 || request.format != stageforge::AudioSampleFormat::Float32) return 2;
    if (request.allow_rate_conversion || request.allow_period_adaptation ||
        request.allow_channel_conversion || request.allow_format_conversion) return 3;

    // Engine-side conversion permission must not turn into endpoint adaptation.
    if (!stageforge::make_engine_native_audio_request(stageforge::AudioDirection::Capture,
            44100.0, 128, 1, "FLOAT_LE", 3, request)) return 4;
    if (request.direction != stageforge::AudioDirection::Capture || request.channels != 1 ||
        request.allow_rate_conversion || request.allow_channel_conversion) return 5;

    // The native endpoint stream has no integer client-format callback contract.
    if (stageforge::make_engine_native_audio_request(stageforge::AudioDirection::Playback,
            48000.0, 256, 2, "S16_LE", 4, request)) return 6;
    if (stageforge::make_engine_native_audio_request(stageforge::AudioDirection::Playback,
            7999.0, 256, 2, "FLOAT_LE", 0, request)) return 7;
    if (stageforge::make_engine_native_audio_request(stageforge::AudioDirection::Playback,
            48000.0, 8, 2, "FLOAT_LE", 0, request)) return 8;
    if (stageforge::make_engine_native_audio_request(stageforge::AudioDirection::Playback,
            48000.0, 256, 33, "FLOAT_LE", 0, request)) return 9;
    if (stageforge::make_engine_native_audio_request(stageforge::AudioDirection::Playback,
            48000.0, 256, 2, "FLOAT_LE", 8, request)) return 10;

    std::cout << "engine native audio request smoke passed\n";
    return 0;
}
