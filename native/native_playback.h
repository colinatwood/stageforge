#pragma once
#include "audio_stream_lifecycle.h"
#include <memory>

namespace stageforge {
// Called with interleaved float32. Must be bounded, allocation-free and noexcept.
// The context must outlive close(). A null callback renders silence.
using PlaybackRender = void (*)(float*, std::uint32_t, std::uint32_t, void*) noexcept;
struct PlaybackStats {
    std::uint64_t callbacks = 0;
    std::uint64_t frames = 0;
    bool native_running = false;
    bool callback_fault = false;
    AudioStreamObservation lifecycle;
    // Last successful OS readback, retained for evidence after close().
    // native_running/lifecycle describe whether it is currently executing.
    AudioPreflightDecision last_verified_configuration;
};

// Owner-thread API, tied to one DeviceExecutionFence lifetime. Owns an exact,
// pinned float32 playback stream. No automatic endpoint substitution, rate or
// channel conversion. Existing device rate/period must match the request; this
// adapter does not change global device settings. Windows uses an owner-thread
// event pump; macOS uses an asynchronous HAL callback with atomic permission.
// Call service() regularly for native stopping after notification revocation.
// In-flight rendering may finish during revocation; stop/close drains native I/O
// before returning. No callback can access the user context after close().
class NativePlaybackStream {
public:
    explicit NativePlaybackStream(PlaybackRender render = nullptr, void* context = nullptr);
    ~NativePlaybackStream();
    NativePlaybackStream(const NativePlaybackStream&) = delete;
    NativePlaybackStream& operator=(const NativePlaybackStream&) = delete;
    bool prepare(const AudioRequest&, const DeviceExecutionFence&);
    bool start(const DeviceExecutionFence&);
    void service(const DeviceExecutionFence&, std::uint32_t wait_ms = 0);
    void close();
    PlaybackStats stats() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
