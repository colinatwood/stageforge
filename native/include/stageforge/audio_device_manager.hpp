#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string_view>

namespace stageforge {

struct AudioEndpointDescriptor {
    std::array<char, 64> id{};
    std::array<char, 128> name{};
    std::array<char, 128> backend_address{};
    std::array<char, 32> backend{};
    bool input{false};
    bool output{false};
    bool connected{false};
};

// Dependency-light discovery layer. It always exposes the null endpoint and,
// on Linux, dynamically loads libasound at runtime to enumerate ALSA PCM hints.
// There is no compile-time ALSA dependency and discovery failure is non-fatal.
class AudioDeviceManager {
public:
    AudioDeviceManager() noexcept = default;

    std::size_t scan() noexcept;
    [[nodiscard]] std::size_t device_count() const noexcept { return count_; }
    [[nodiscard]] const AudioEndpointDescriptor* device(std::size_t index) const noexcept;
    [[nodiscard]] const AudioEndpointDescriptor* find(std::string_view id) const noexcept;

private:
    void add_null() noexcept;
    void scan_platform() noexcept;
    void add_endpoint(std::string_view name, std::string_view address, std::string_view backend, bool input, bool output) noexcept;

    static constexpr std::size_t max_devices = 64;
    std::array<AudioEndpointDescriptor, max_devices> devices_{};
    std::size_t count_{0};
};

} // namespace stageforge
