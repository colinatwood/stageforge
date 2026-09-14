#pragma once
#include "audio_preflight.h"
#include "device_execution_fence.h"
#include <cstdint>

namespace stageforge {

enum class AudioStreamState {
    Closed,
    Prepared,
    Running,
    Stopped,
    Fenced,
};

struct AudioStreamObservation {
    AudioStreamState state = AudioStreamState::Closed;
    bool callback_execution_allowed = false;
    bool stop_required = false;
    bool explicit_rearm_required = true;
    std::uint64_t generation = 0;
};

// Control-thread lifecycle contract between audio preflight and the device
// execution fence. This object owns no OS audio resources. A platform adapter
// must synchronously stop its native stream whenever reconcile() reports
// stop_required=true.
class GuardedAudioStreamLifecycle {
public:
    AudioStreamObservation observation() const noexcept;

    bool prepare(const AudioPreflightDecision& decision, const FenceObservation& fence);
    bool start(const FenceObservation& fence);
    AudioStreamObservation reconcile(const FenceObservation& fence) noexcept;
    void mark_stopped() noexcept;
    void close() noexcept;

private:
    void transition(AudioStreamState next) noexcept;

    AudioStreamState state_ = AudioStreamState::Closed;
    bool stop_required_ = false;
    std::uint64_t generation_ = 0;
};

struct SoftwareAudioClockResult {
    bool available = false;
    bool started = false;
    bool stopped = false;
    bool hardware_output_used = false;
    std::uint64_t callback_count = 0;
    std::uint64_t rendered_frames = 0;
};

// macOS-only software clock based on Apple's Generic Output Audio Unit. It is
// deliberately not connected to an audio device. Other platforms return
// available=false rather than substituting fake hardware.
SoftwareAudioClockResult run_software_audio_clock(std::uint32_t sample_rate_hz,
                                                  std::uint32_t frames_per_slice,
                                                  std::uint32_t run_milliseconds);

const char* audio_stream_state_name(AudioStreamState state);

}
