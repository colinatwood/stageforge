#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string_view>

namespace stageforge {

// Target-OS MIDI byte ingress. Control-thread attach/detach owns exactly one
// endpoint selected by DeviceMonitor's one-way native hash. OS callbacks only
// append bytes to a bounded lock-free SPSC ring; poll_bytes() drains without
// allocation. No endpoint is selected by name, index, or system default.
class NativeMidiInput {
public:
    NativeMidiInput();
    ~NativeMidiInput();
    NativeMidiInput(const NativeMidiInput&) = delete;
    NativeMidiInput& operator=(const NativeMidiInput&) = delete;

    [[nodiscard]] bool attach(std::string_view native_hash) noexcept;
    void detach() noexcept;
    [[nodiscard]] bool attached() const noexcept;
    std::size_t poll_bytes(std::uint8_t* destination, std::size_t capacity) noexcept;
    [[nodiscard]] std::uint64_t dropped_bytes() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace stageforge
