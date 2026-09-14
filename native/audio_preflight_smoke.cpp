#include "audio_preflight.h"

#include <iostream>
#include <stdexcept>
#include <string>

using namespace stageforge;

namespace {
const char* boolean(bool value) { return value ? "true" : "false"; }

AudioRequest exact_request(AudioDirection direction, const AudioHostCapabilities& capabilities) {
    AudioRequest request{};
    request.direction = direction;
    request.sample_rate_hz = capabilities.native_sample_rate_hz;
    request.period_frames = capabilities.default_period_frames;
    request.channels = direction == AudioDirection::Playback ? capabilities.output_channels : capabilities.input_channels;
    request.format = capabilities.client_format;
    return request;
}

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void print_live(const char* key, AudioDirection direction, const AudioHostCapabilities& capabilities,
                const AudioPreflightDecision& decision) {
    std::cout << "\"" << key << "\":{";
    std::cout << "\"endpointPresent\":" << boolean(capabilities.endpoint_present) << ',';
    std::cout << "\"backend\":\"" << capabilities.backend << "\",";
    std::cout << "\"endpointIdentityHash\":\"" << capabilities.endpoint_identity_hash << "\",";
    std::cout << "\"endpointIdentityStrong\":" << boolean(capabilities.endpoint_identity_strong) << ',';
    std::cout << "\"nativeSampleRateHz\":" << capabilities.native_sample_rate_hz << ',';
    std::cout << "\"defaultPeriodFrames\":" << capabilities.default_period_frames << ',';
    std::cout << "\"minimumPeriodFrames\":" << capabilities.minimum_period_frames << ',';
    std::cout << "\"maximumPeriodFrames\":" << capabilities.maximum_period_frames << ',';
    std::cout << "\"channels\":" << (direction == AudioDirection::Playback ? capabilities.output_channels : capabilities.input_channels) << ',';
    std::cout << "\"clientFormat\":\"" << audio_sample_format_name(capabilities.client_format) << "\",";
    std::cout << "\"preflightStatus\":\"" << audio_preflight_status_name(decision.status) << "\",";
    std::cout << "\"exactHostPlanQualified\":" << boolean(
        capabilities.endpoint_present ? decision.status == AudioPreflightStatus::Exact : decision.status == AudioPreflightStatus::NoEndpoint);
    std::cout << '}';
}
}

int main() {
    try {
        AudioHostCapabilities synthetic{};
        synthetic.backend = "synthetic";
        synthetic.endpoint_present = true;
        synthetic.endpoint_identity_hash = "sha256:synthetic";
        synthetic.endpoint_identity_strong = true;
        synthetic.native_sample_rate_hz = 48000;
        synthetic.default_period_frames = 256;
        synthetic.minimum_period_frames = 128;
        synthetic.maximum_period_frames = 512;
        synthetic.input_channels = 2;
        synthetic.output_channels = 2;
        synthetic.client_format = AudioSampleFormat::Float32;
        synthetic.supported_sample_rates.push_back({48000.0, 48000.0});

        AudioRequest exact{};
        auto exact_decision = evaluate_audio_preflight(exact, synthetic);
        require(exact_decision.status == AudioPreflightStatus::Exact, "exact preflight did not remain exact");
        require(!exact_decision.rate_conversion && !exact_decision.period_adaptation &&
            !exact_decision.channel_conversion && !exact_decision.format_conversion,
            "exact preflight unexpectedly adapted");

        AudioRequest adapted{};
        adapted.sample_rate_hz = 44100;
        adapted.period_frames = 64;
        adapted.channels = 1;
        adapted.format = AudioSampleFormat::Int16;
        adapted.allow_rate_conversion = true;
        adapted.allow_period_adaptation = true;
        adapted.allow_channel_conversion = true;
        adapted.allow_format_conversion = true;
        auto adapted_decision = evaluate_audio_preflight(adapted, synthetic);
        require(adapted_decision.status == AudioPreflightStatus::ExplicitAdaptation, "explicit adaptation was not reported");
        require(adapted_decision.rate_conversion && adapted_decision.period_adaptation &&
            adapted_decision.channel_conversion && adapted_decision.format_conversion,
            "explicit adaptation plan is incomplete");
        require(adapted_decision.configured_sample_rate_hz == 48000 && adapted_decision.configured_period_frames == 256 &&
            adapted_decision.configured_channels == 2 && adapted_decision.configured_format == AudioSampleFormat::Float32,
            "configured adaptation plan does not match host contract");

        AudioRequest denied = adapted;
        denied.allow_rate_conversion = false;
        denied.allow_period_adaptation = false;
        denied.allow_channel_conversion = false;
        denied.allow_format_conversion = false;
        auto denied_decision = evaluate_audio_preflight(denied, synthetic);
        require(denied_decision.status == AudioPreflightStatus::Unsupported, "implicit conversion was not rejected");

        AudioHostCapabilities absent{};
        absent.backend = "synthetic";
        auto absent_decision = evaluate_audio_preflight(exact, absent);
        require(absent_decision.status == AudioPreflightStatus::NoEndpoint, "missing endpoint did not fail closed");

        const auto playback = probe_default_audio_endpoint(AudioDirection::Playback);
        const auto capture = probe_default_audio_endpoint(AudioDirection::Capture);
        const auto playback_decision = evaluate_audio_preflight(
            playback.endpoint_present ? exact_request(AudioDirection::Playback, playback) : AudioRequest{}, playback);
        AudioRequest capture_request{};
        capture_request.direction = AudioDirection::Capture;
        if (capture.endpoint_present) capture_request = exact_request(AudioDirection::Capture, capture);
        const auto capture_decision = evaluate_audio_preflight(capture_request, capture);

        const bool playback_probe_ok = playback.endpoint_present
            ? playback_decision.status == AudioPreflightStatus::Exact
            : playback_decision.status == AudioPreflightStatus::NoEndpoint;
        const bool capture_probe_ok = capture.endpoint_present
            ? capture_decision.status == AudioPreflightStatus::Exact
            : capture_decision.status == AudioPreflightStatus::NoEndpoint;
        require(playback_probe_ok && capture_probe_ok, "live host preflight did not produce bounded exact/no-endpoint result");

        std::cout << '{';
        std::cout << "\"syntheticExactQualified\":true,";
        std::cout << "\"syntheticExplicitAdaptationQualified\":true,";
        std::cout << "\"implicitConversionRejected\":true,";
        std::cout << "\"missingEndpointRejected\":true,";
        print_live("playback", AudioDirection::Playback, playback, playback_decision);
        std::cout << ',';
        print_live("capture", AudioDirection::Capture, capture, capture_decision);
        std::cout << ',';
        std::cout << "\"physicalOutputsArmed\":false,";
        std::cout << "\"audioStreamingQualified\":false,";
        std::cout << "\"physicalHardwareQualified\":false";
        std::cout << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
