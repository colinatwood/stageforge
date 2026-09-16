#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string_view>

namespace stageforge {

struct MidiInputMessage {
    std::uint64_t show_time_ns{0};
    std::uint8_t status{0};
    std::uint8_t data1{0};
    std::uint8_t data2{0};
};

// Allocation-free MIDI 1 byte-stream parser. It supports channel voice
// messages, running status, realtime bytes interleaved with messages, and
// skips SysEx payloads. System-common messages are consumed but not emitted in
// this first input slice because StageForge currently routes three-byte channel
// events through its public control contract.
class MidiByteParser {
public:
    [[nodiscard]] bool feed(std::uint8_t byte, std::uint64_t show_time_ns, MidiInputMessage& out) noexcept;
    void reset() noexcept;

private:
    [[nodiscard]] static std::uint8_t data_length(std::uint8_t status) noexcept;

    std::uint8_t running_status_{0};
    std::uint8_t message_status_{0};
    std::array<std::uint8_t, 2> data_{};
    std::uint8_t expected_{0};
    std::uint8_t received_{0};
    bool in_sysex_{false};
};

struct MidiDeviceDescriptor {
    std::array<char, 64> id{};
    std::array<char, 128> name{};
    std::array<char, 192> path{};
    bool input{true};
    bool connected{true};
};

struct CapturedMidiInput {
    std::array<char, 64> device_id{};
    std::array<char, 64> player_id{};
    MidiInputMessage message{};
};

struct MidiIngressAuditStatus {
    std::uint64_t polls{0}, bytes{0}, messages{0}, queue_drops{0}, injected_messages{0}, max_poll_duration_ns{0};
    bool physical_outputs_armed{false};
};

// Small platform-facing input registry. Registry/open/close operations belong
// on the control thread. poll() is non-blocking. Linux uses raw /dev/snd MIDI
// character devices without linking libasound. Unsupported platforms simply
// report zero devices until a native backend is supplied.
class MidiInputManager {
public:
    MidiInputManager() noexcept;
    ~MidiInputManager();

    MidiInputManager(const MidiInputManager&) = delete;
    MidiInputManager& operator=(const MidiInputManager&) = delete;

    std::size_t scan() noexcept;
    [[nodiscard]] std::size_t device_count() const noexcept { return device_count_; }
    [[nodiscard]] const MidiDeviceDescriptor* device(std::size_t index) const noexcept;
    [[nodiscard]] bool attached(std::string_view device_id) const noexcept;

    [[nodiscard]] bool attach(std::string_view device_id, std::string_view player_id) noexcept;
    [[nodiscard]] bool detach(std::string_view device_id) noexcept;
    [[nodiscard]] std::size_t attached_count() const noexcept;

    // Reads all currently available bytes from attached devices and appends
    // parsed events to a bounded queue. Returns newly captured event count.
    std::size_t poll(std::uint64_t show_time_ns) noexcept;
    [[nodiscard]] bool pop(CapturedMidiInput& out) noexcept;
    [[nodiscard]] bool inject(std::string_view device_id, std::string_view player_id, const MidiInputMessage& message) noexcept;
    [[nodiscard]] std::size_t queued() const noexcept { return queue_size_; }
    [[nodiscard]] MidiIngressAuditStatus audit_status() const noexcept;

private:
    struct DeviceSlot {
        MidiDeviceDescriptor descriptor{};
        std::array<char, 64> player_id{};
        MidiByteParser parser{};
        int handle{-1};
        bool attached{false};
    };

    [[nodiscard]] DeviceSlot* find_slot(std::string_view device_id) noexcept;
    [[nodiscard]] const DeviceSlot* find_slot(std::string_view device_id) const noexcept;
    void close_slot(DeviceSlot& slot) noexcept;
    [[nodiscard]] bool queue(const CapturedMidiInput& event) noexcept;

    static constexpr std::size_t max_devices = 32;
    static constexpr std::size_t queue_capacity = 2048;
    std::array<DeviceSlot, max_devices> devices_{};
    std::size_t device_count_{0};
    std::array<CapturedMidiInput, queue_capacity> queue_{};
    std::size_t queue_head_{0};
    std::size_t queue_tail_{0};
    std::size_t queue_size_{0};
    std::atomic<std::uint64_t> audit_polls_{0},audit_bytes_{0},audit_messages_{0},audit_queue_drops_{0},audit_injected_{0},audit_max_poll_ns_{0};
};

} // namespace stageforge
