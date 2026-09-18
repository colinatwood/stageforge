#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string_view>

namespace stageforge {
#if defined(_WIN32) || defined(__APPLE__)
class NativeMidiInput;
struct NativeMidiInputDeleter { void operator()(NativeMidiInput*) const noexcept; };
#else
struct NullNativeMidiInput { void reset() noexcept {} };
#endif
struct MidiInputMessage { std::uint64_t show_time_ns{0}; std::uint8_t status{0},data1{0},data2{0}; };
class MidiByteParser { public: [[nodiscard]] bool feed(std::uint8_t,std::uint64_t,MidiInputMessage&) noexcept; void reset() noexcept; private: [[nodiscard]] static std::uint8_t data_length(std::uint8_t) noexcept; std::uint8_t running_status_{0},message_status_{0}; std::array<std::uint8_t,2> data_{}; std::uint8_t expected_{0},received_{0}; bool in_sysex_{false}; };
// Target-OS IDs include backend/type/hash framing plus a 64-hex SHA-256 digest,
// so 64 bytes is insufficient even though the digest alone fits. Keep the exact
// identity intact end-to-end; truncating it would silently defeat ownership fences.
struct MidiDeviceDescriptor { std::array<char,128> id{}; std::array<char,128> name{}; std::array<char,256> path{}; bool input{true}; bool connected{true}; };
struct CapturedMidiInput { std::array<char,128> device_id{}; std::array<char,64> player_id{}; MidiInputMessage message{}; };
struct MidiIngressAuditStatus { std::uint64_t polls{0},bytes{0},messages{0},queue_drops{0},injected_messages{0},max_poll_duration_ns{0}; bool physical_outputs_armed{false}; };

class MidiInputManager {
public:
    MidiInputManager() noexcept; ~MidiInputManager(); MidiInputManager(const MidiInputManager&)=delete; MidiInputManager& operator=(const MidiInputManager&)=delete;
    std::size_t scan() noexcept; [[nodiscard]] std::size_t device_count() const noexcept{return device_count_;} [[nodiscard]] const MidiDeviceDescriptor* device(std::size_t) const noexcept; [[nodiscard]] bool attached(std::string_view) const noexcept;
    [[nodiscard]] bool attach(std::string_view,std::string_view) noexcept; [[nodiscard]] bool detach(std::string_view) noexcept; [[nodiscard]] std::size_t attached_count() const noexcept; std::size_t poll(std::uint64_t) noexcept;
    [[nodiscard]] bool pop(CapturedMidiInput&) noexcept; [[nodiscard]] bool inject(std::string_view,std::string_view,const MidiInputMessage&) noexcept; [[nodiscard]] std::size_t queued() const noexcept{return queue_size_;} [[nodiscard]] MidiIngressAuditStatus audit_status() const noexcept;
private:
    struct DeviceSlot { MidiDeviceDescriptor descriptor{}; std::array<char,64> player_id{}; MidiByteParser parser{}; int handle{-1};
#if defined(_WIN32) || defined(__APPLE__)
        std::unique_ptr<NativeMidiInput, NativeMidiInputDeleter> native{};
#else
        NullNativeMidiInput native{};
#endif
        std::uint64_t native_drops_seen{0}; bool attached{false}; };
    [[nodiscard]] DeviceSlot* find_slot(std::string_view) noexcept; [[nodiscard]] const DeviceSlot* find_slot(std::string_view) const noexcept; void close_slot(DeviceSlot&) noexcept; [[nodiscard]] bool queue(const CapturedMidiInput&) noexcept;
    static constexpr std::size_t max_devices=32,queue_capacity=2048; std::array<DeviceSlot,max_devices> devices_{}; std::size_t device_count_{0}; std::array<CapturedMidiInput,queue_capacity> queue_{}; std::size_t queue_head_{0},queue_tail_{0},queue_size_{0};
    std::atomic<std::uint64_t> audit_polls_{0},audit_bytes_{0},audit_messages_{0},audit_queue_drops_{0},audit_injected_{0},audit_max_poll_ns_{0};
};
} // namespace stageforge
