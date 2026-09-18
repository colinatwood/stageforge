#include "native_midi_input.h"
#include "device_identity.h"

#include <array>
#include <atomic>
#include <cstring>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#include <mmsystem.h>
#include <mmddk.h>
#elif defined(__APPLE__)
#include <CoreMIDI/CoreMIDI.h>
#endif

namespace stageforge {
namespace {
constexpr std::size_t ring_capacity = 8192;
}

struct NativeMidiInput::Impl {
    std::array<std::uint8_t, ring_capacity> ring{};
    std::atomic<std::size_t> write{0};
    std::atomic<std::size_t> read{0};
    std::atomic<std::uint64_t> drops{0};
#if defined(_WIN32) || defined(__APPLE__)
    std::atomic<bool> revoked{false};
#endif
#ifdef _WIN32
    HMIDIIN input = nullptr;
#elif defined(__APPLE__)
    MIDIClientRef client = 0;
    MIDIPortRef port = 0;
    MIDIEndpointRef source = 0;
    std::atomic<std::uintptr_t> selected_source{0};
#endif

    void push(std::uint8_t byte) noexcept {
        const auto current = write.load(std::memory_order_relaxed);
        const auto next = (current + 1) % ring_capacity;
        if (next == read.load(std::memory_order_acquire)) {
            drops.fetch_add(1, std::memory_order_relaxed);
            return;
        }
        ring[current] = byte;
        write.store(next, std::memory_order_release);
    }

#ifdef _WIN32
    static void CALLBACK callback(HMIDIIN, UINT message, DWORD_PTR instance, DWORD_PTR first, DWORD_PTR) noexcept {
        auto* self = reinterpret_cast<Impl*>(instance);
        if (!self) return;
        if (message == MIM_CLOSE || message == MIM_ERROR || message == MIM_LONGERROR) {
            self->revoked.store(true, std::memory_order_release);
            return;
        }
        if (message != MIM_DATA || self->revoked.load(std::memory_order_acquire)) return;
        const auto packed = static_cast<std::uint32_t>(first);
        const auto status = static_cast<std::uint8_t>(packed & 0xffU);
        self->push(status);
        const auto high = static_cast<std::uint8_t>(status & 0xf0U);
        const auto data = (high == 0xc0U || high == 0xd0U) ? 1U : (high >= 0x80U && high <= 0xe0U ? 2U : 0U);
        if (data > 0) self->push(static_cast<std::uint8_t>((packed >> 8U) & 0x7fU));
        if (data > 1) self->push(static_cast<std::uint8_t>((packed >> 16U) & 0x7fU));
    }
#elif defined(__APPLE__)
    static void notify(const MIDINotification* notification, void* context) noexcept {
        auto* self = static_cast<Impl*>(context);
        if (!self || !notification || notification->messageID != kMIDIMsgObjectRemoved) return;
        const auto* removed = reinterpret_cast<const MIDIObjectAddRemoveNotification*>(notification);
        const auto selected = self->selected_source.load(std::memory_order_acquire);
        if (selected != 0 && static_cast<std::uintptr_t>(removed->child) == selected) {
            self->revoked.store(true, std::memory_order_release);
        }
    }

    static void callback(const MIDIPacketList* packets, void* context, void*) noexcept {
        auto* self = static_cast<Impl*>(context);
        if (!self || !packets || self->revoked.load(std::memory_order_acquire)) return;
        const MIDIPacket* packet = &packets->packet[0];
        for (UInt32 p = 0; p < packets->numPackets; ++p) {
            for (UInt16 i = 0; i < packet->length; ++i) self->push(packet->data[i]);
            packet = MIDIPacketNext(packet);
        }
    }
#endif
};

NativeMidiInput::NativeMidiInput() : impl_(std::make_unique<Impl>()) {}
NativeMidiInput::~NativeMidiInput() { detach(); }

bool NativeMidiInput::attach(std::string_view native_hash) noexcept {
    detach();
    if (native_hash.empty() || native_hash.rfind("sha256:", 0) != 0) return false;
    impl_->read.store(0, std::memory_order_relaxed);
    impl_->write.store(0, std::memory_order_relaxed);
    impl_->drops.store(0, std::memory_order_relaxed);
#ifdef _WIN32
    impl_->revoked.store(false, std::memory_order_relaxed);
    const auto count = midiInGetNumDevs();
    for (UINT index = 0; index < count; ++index) {
        ULONG bytes = 0;
        std::string interface_name;
        const auto query = [&](UINT msg, DWORD_PTR first, DWORD_PTR second) {
            return midiInMessage(reinterpret_cast<HMIDIIN>(static_cast<UINT_PTR>(index)), msg, first, second);
        };
        if (query(DRV_QUERYDEVICEINTERFACESIZE, reinterpret_cast<DWORD_PTR>(&bytes), 0) == MMSYSERR_NOERROR &&
            bytes >= sizeof(wchar_t) && bytes <= 65536 && bytes % sizeof(wchar_t) == 0) {
            std::vector<wchar_t> buffer(bytes / sizeof(wchar_t), L'\0');
            if (query(DRV_QUERYDEVICEINTERFACE, reinterpret_cast<DWORD_PTR>(buffer.data()), bytes) == MMSYSERR_NOERROR && buffer.back() == L'\0') {
                const int needed = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, buffer.data(), -1, nullptr, 0, nullptr, nullptr);
                if (needed > 1) {
                    std::string text(static_cast<std::size_t>(needed), '\0');
                    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, buffer.data(), -1, text.data(), needed, nullptr, nullptr)) {
                        text.pop_back(); interface_name = std::move(text);
                    }
                }
            }
        }
        if (interface_name.empty()) continue;
        const auto candidate = sha256_token("winmm-native:input:" + interface_name + ":" + std::to_string(index));
        if (candidate != native_hash) continue;
        HMIDIIN handle = nullptr;
        if (midiInOpen(&handle, index, reinterpret_cast<DWORD_PTR>(&Impl::callback), reinterpret_cast<DWORD_PTR>(impl_.get()), CALLBACK_FUNCTION) != MMSYSERR_NOERROR) return false;
        impl_->input = handle;
        if (midiInStart(handle) != MMSYSERR_NOERROR) { midiInClose(handle); impl_->input = nullptr; return false; }
        return true;
    }
#elif defined(__APPLE__)
    impl_->revoked.store(false, std::memory_order_relaxed);
    impl_->selected_source.store(0, std::memory_order_relaxed);
    if (MIDIClientCreate(CFSTR("StageForge MIDI Input"), &Impl::notify, impl_.get(), &impl_->client) != noErr) return false;
    if (MIDIInputPortCreate(impl_->client, CFSTR("StageForge MIDI Input Port"), &Impl::callback, impl_.get(), &impl_->port) != noErr) { detach(); return false; }
    const auto count = MIDIGetNumberOfSources();
    for (ItemCount index = 0; index < count; ++index) {
        const auto source = MIDIGetSource(index);
        if (!source) continue;
        const auto candidate = sha256_token("coremidi-native:" + std::to_string(static_cast<std::uint64_t>(source)) + ":in");
        if (candidate != native_hash) continue;
        if (MIDIPortConnectSource(impl_->port, source, nullptr) != noErr) { detach(); return false; }
        impl_->source = source;
        impl_->selected_source.store(static_cast<std::uintptr_t>(source), std::memory_order_release);
        return true;
    }
    detach();
#endif
    return false;
}

void NativeMidiInput::detach() noexcept {
#ifdef _WIN32
    if (impl_->input) { midiInStop(impl_->input); midiInReset(impl_->input); midiInClose(impl_->input); impl_->input = nullptr; }
    impl_->revoked.store(false, std::memory_order_relaxed);
#elif defined(__APPLE__)
    impl_->revoked.store(true, std::memory_order_release);
    impl_->selected_source.store(0, std::memory_order_release);
    if (impl_->port && impl_->source) MIDIPortDisconnectSource(impl_->port, impl_->source);
    impl_->source = 0;
    if (impl_->port) { MIDIPortDispose(impl_->port); impl_->port = 0; }
    if (impl_->client) { MIDIClientDispose(impl_->client); impl_->client = 0; }
#endif
}

bool NativeMidiInput::attached() const noexcept {
#ifdef _WIN32
    return impl_->input != nullptr && !impl_->revoked.load(std::memory_order_acquire);
#elif defined(__APPLE__)
    return impl_->source != 0 && !impl_->revoked.load(std::memory_order_acquire);
#else
    return false;
#endif
}

std::size_t NativeMidiInput::poll_bytes(std::uint8_t* destination, std::size_t capacity) noexcept {
    if (!destination || capacity == 0 || !attached()) return 0;
    std::size_t count = 0;
    auto current = impl_->read.load(std::memory_order_relaxed);
    const auto end = impl_->write.load(std::memory_order_acquire);
    while (current != end && count < capacity) {
        destination[count++] = impl_->ring[current];
        current = (current + 1) % ring_capacity;
    }
    impl_->read.store(current, std::memory_order_release);
    return count;
}

std::uint64_t NativeMidiInput::dropped_bytes() const noexcept { return impl_->drops.load(std::memory_order_relaxed); }

} // namespace stageforge
