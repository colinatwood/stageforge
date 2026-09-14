#pragma once
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace stageforge {
struct DeviceIdentity {
    std::string hash;
    // Windows endpoint IDs are opaque installation-scoped IDs, not StableId.
    // CoreAudio UID persistence is an OS identity contract, not hardware proof.
    enum class Scope { WindowsEndpoint, CoreAudioUID } scope;
};
struct DeviceSnapshot {
    unsigned device_count;
    bool default_input_present;
    bool default_output_present;
    std::vector<DeviceIdentity> identities;
};

// Control-thread API. Callbacks only advance an atomic revision; callers refresh
// snapshots off the audio thread. No stream is opened or automatically restarted.
// Construction, start, snapshot, stop and destruction must use the same thread.
class DeviceMonitor {
public:
    DeviceMonitor();
    ~DeviceMonitor();
    DeviceMonitor(const DeviceMonitor&) = delete;
    DeviceMonitor& operator=(const DeviceMonitor&) = delete;
    void start(); // Idempotent; subscribe before taking the initial snapshot.
    void stop();  // Idempotent; errors are reported to the caller.
    DeviceSnapshot snapshot() const;
    std::uint64_t revision() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
