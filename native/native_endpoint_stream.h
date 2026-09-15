#pragma once
#include "audio_stream_lifecycle.h"
#include <memory>

namespace stageforge {
// Called with interleaved float32. Must be bounded, allocation-free and noexcept.
// The context must outlive close(). A null callback renders silence.
struct CapturePacketInfo {
    bool discontinuity = false;
    bool timestamp_valid = false;
    double sample_position = 0;
};
// Buffer is borrowed for this call only. Copying/retaining it is the consumer's
// responsibility; the adapter retains no recording. Must be bounded/noexcept.
using CaptureReceive = void (*)(const float*, std::uint32_t, std::uint32_t, const CapturePacketInfo&, void*) noexcept;
using PlaybackRender = void (*)(float*, std::uint32_t, std::uint32_t, void*) noexcept;
struct EndpointStreamStats {
    std::uint64_t callbacks = 0;
    std::uint64_t frames = 0;
    bool native_running = false;
    bool callback_fault = false;
    AudioStreamObservation lifecycle;
    // Last successful OS readback, retained for evidence after close().
    // native_running/lifecycle describe whether it is currently executing.
    AudioPreflightDecision last_verified_configuration;
    std::uint64_t discontinuities = 0;
};

// Owner-thread API, tied to one DeviceExecutionFence lifetime. Owns an exact,
// pinned float32 input or output stream. No automatic endpoint substitution, rate or
// channel conversion. Existing device rate/period must match the request; this
// adapter does not change global device settings. Windows uses an owner-thread
// event pump; macOS uses an asynchronous HAL callback with atomic permission.
// Call service() regularly for native stopping after notification revocation.
// In-flight rendering may finish during revocation; stop/close drains native I/O
// before returning. No callback can access the user context after close().
class NativeEndpointStream {
public:
    virtual ~NativeEndpointStream();
    NativeEndpointStream(const NativeEndpointStream&) = delete;
    NativeEndpointStream& operator=(const NativeEndpointStream&) = delete;
    bool prepare(const AudioRequest&, const DeviceExecutionFence&);
    bool start(const DeviceExecutionFence&);
    void service(const DeviceExecutionFence&, std::uint32_t wait_ms = 0);
    void close();
    EndpointStreamStats stats() const;
protected:
    NativeEndpointStream(AudioDirection, PlaybackRender, CaptureReceive, void*);
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
