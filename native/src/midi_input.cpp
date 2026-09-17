#include "stageforge/midi_input.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <new>
#include <string>

#if defined(__linux__)
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#elif defined(_WIN32) || defined(__APPLE__)
#include "device_monitor.h"
#include "native_midi_input.h"
#endif

namespace stageforge {
namespace {

template <std::size_t N>
void copy_text(std::array<char, N>& target, std::string_view source) noexcept {
    const auto count = std::min(source.size(), N - 1);
    if (count > 0) std::memcpy(target.data(), source.data(), count);
    target[count] = '\0';
}

bool same_text(const auto& buffer, std::string_view value) noexcept { return std::string_view(buffer.data()) == value; }

#if defined(__linux__)
bool parse_linux_raw_midi_name(const char* name, unsigned int& card, unsigned int& device) noexcept {
    if (std::strncmp(name, "midiC", 5) != 0) return false;
    char tail = '\0';
    return std::sscanf(name, "midiC%uD%u%c", &card, &device, &tail) == 2;
}
#elif defined(_WIN32) || defined(__APPLE__)
std::string target_midi_id(const DeviceRecord& record, std::string_view backend) {
    std::string digest = record.native_hash;
    constexpr std::string_view prefix{"sha256:"};
    if (digest.rfind(prefix, 0) == 0) digest.erase(0, prefix.size());
    if (digest.size() > 40) digest.resize(40);
    return std::string(backend) + "-" + digest;
}

std::string target_midi_identity(const DeviceRecord& record, std::string_view backend) {
    return std::string("backend=") + std::string(backend) + ";native=" + record.native_hash +
        ";persistent=" + record.persistent_hash + ";strength=" + identity_strength_name(record.identity_strength) +
        ";auto=" + (record.automatic_reconnect ? "1" : "0");
}

std::string_view native_hash_from_identity(std::string_view identity) noexcept {
    constexpr std::string_view marker{"native="};
    const auto begin = identity.find(marker);
    if (begin == std::string_view::npos) return {};
    const auto value_begin = begin + marker.size();
    const auto end = identity.find(';', value_begin);
    const auto value = identity.substr(value_begin, end == std::string_view::npos ? identity.size() - value_begin : end - value_begin);
    return value.rfind("sha256:", 0) == 0 ? value : std::string_view{};
}
#endif
} // namespace

std::uint8_t MidiByteParser::data_length(std::uint8_t status) noexcept {
    const auto high = static_cast<std::uint8_t>(status & 0xF0U);
    if (high >= 0x80U && high <= 0xE0U) return (high == 0xC0U || high == 0xD0U) ? 1U : 2U;
    switch (status) { case 0xF1U: return 1U; case 0xF2U: return 2U; case 0xF3U: return 1U; default: return 0U; }
}

void MidiByteParser::reset() noexcept { running_status_=0; message_status_=0; expected_=0; received_=0; in_sysex_=false; }

bool MidiByteParser::feed(std::uint8_t byte, std::uint64_t show_time_ns, MidiInputMessage& out) noexcept {
    if (byte >= 0xF8U) return false;
    if (in_sysex_) { if (byte == 0xF7U) in_sysex_ = false; return false; }
    if ((byte & 0x80U) != 0U) {
        received_=0; message_status_=byte; expected_=data_length(byte);
        if (byte == 0xF0U) { in_sysex_=true; running_status_=0; expected_=0; return false; }
        if (byte < 0xF0U) running_status_=byte; else running_status_=0;
        return false;
    }
    if (expected_ == 0) {
        if (running_status_ == 0) return false;
        message_status_=running_status_; expected_=data_length(message_status_); received_=0;
    }
    if (received_ < data_.size()) data_[received_] = static_cast<std::uint8_t>(byte & 0x7FU);
    ++received_; if (received_ < expected_) return false;
    const auto status=message_status_; const auto channel_voice=status < 0xF0U;
    out = MidiInputMessage{show_time_ns,status,data_[0],expected_ > 1 ? data_[1] : static_cast<std::uint8_t>(0)};
    received_=0;
    if (channel_voice && running_status_ != 0) { message_status_=running_status_; expected_=data_length(running_status_); }
    else { message_status_=0; expected_=0; }
    return channel_voice;
}

MidiInputManager::MidiInputManager() noexcept = default;
MidiInputManager::~MidiInputManager() { for (std::size_t i=0;i<device_count_;++i) close_slot(devices_[i]); }
const MidiDeviceDescriptor* MidiInputManager::device(std::size_t index) const noexcept { return index < device_count_ ? &devices_[index].descriptor : nullptr; }

MidiInputManager::DeviceSlot* MidiInputManager::find_slot(std::string_view id) noexcept {
    for (std::size_t i=0;i<device_count_;++i) if (same_text(devices_[i].descriptor.id,id)) return &devices_[i];
    return nullptr;
}
const MidiInputManager::DeviceSlot* MidiInputManager::find_slot(std::string_view id) const noexcept {
    for (std::size_t i=0;i<device_count_;++i) if (same_text(devices_[i].descriptor.id,id)) return &devices_[i];
    return nullptr;
}
bool MidiInputManager::attached(std::string_view id) const noexcept { const auto* slot=find_slot(id); return slot && slot->attached; }

void MidiInputManager::close_slot(DeviceSlot& slot) noexcept {
#if defined(__linux__)
    if (slot.handle >= 0) ::close(slot.handle);
#elif defined(_WIN32) || defined(__APPLE__)
    if (slot.native) slot.native->detach();
#endif
    slot.handle=-1; slot.native.reset(); slot.native_drops_seen=0; slot.attached=false; slot.player_id[0]='\0'; slot.parser.reset();
}

std::size_t MidiInputManager::scan() noexcept {
    std::array<DeviceSlot,max_devices> found{}; std::size_t found_count=0;
#if defined(__linux__)
    DIR* directory=::opendir("/dev/snd");
    if (directory) {
        while (auto* entry=::readdir(directory)) {
            if (found_count>=max_devices) break;
            unsigned int card=0,device_number=0; if (!parse_linux_raw_midi_name(entry->d_name,card,device_number)) continue;
            char id[64]{},path[192]{},name[128]{};
            std::snprintf(id,sizeof(id),"linux-raw-%u-%u",card,device_number);
            std::snprintf(path,sizeof(path),"/dev/snd/midiC%uD%u",card,device_number);
            std::snprintf(name,sizeof(name),"Linux Raw MIDI C%u D%u",card,device_number);
            auto& slot=found[found_count++]; copy_text(slot.descriptor.id,id); copy_text(slot.descriptor.path,path); copy_text(slot.descriptor.name,name);
            slot.descriptor.connected=true; slot.descriptor.input=true;
            if (auto* existing=find_slot(id); existing && existing->attached) {
                slot.handle=existing->handle; existing->handle=-1; slot.attached=true; slot.player_id=existing->player_id; slot.parser=existing->parser;
            }
        }
        ::closedir(directory);
    }
#elif defined(_WIN32) || defined(__APPLE__)
    try {
        DeviceMonitor monitor; monitor.start(); const auto snapshot=monitor.snapshot(); monitor.stop();
#if defined(_WIN32)
        constexpr std::string_view backend="windows-midi";
#else
        constexpr std::string_view backend="coremidi";
#endif
        for (const auto& record:snapshot.devices) {
            if (found_count>=max_devices) break; if (record.kind!=DeviceKind::Midi || !record.input) continue;
            auto& slot=found[found_count++]; const auto id=target_midi_id(record,backend);
            copy_text(slot.descriptor.id,id); copy_text(slot.descriptor.path,target_midi_identity(record,backend));
#if defined(_WIN32)
            copy_text(slot.descriptor.name,"Windows MIDI Endpoint");
#else
            copy_text(slot.descriptor.name,"CoreMIDI Endpoint");
#endif
            slot.descriptor.connected=true; slot.descriptor.input=true;
            if (auto* existing=find_slot(id); existing && existing->attached) {
                slot.native=std::move(existing->native); slot.native_drops_seen=existing->native_drops_seen;
                slot.attached=slot.native && slot.native->attached(); slot.player_id=existing->player_id; slot.parser=existing->parser;
            }
        }
    } catch (...) { found_count=0; }
#endif
    for (std::size_t i=0;i<device_count_;++i) close_slot(devices_[i]);
    devices_=std::move(found); device_count_=found_count; return device_count_;
}

bool MidiInputManager::attach(std::string_view device_id,std::string_view player_id) noexcept {
    auto* slot=find_slot(device_id); if (!slot || player_id.empty() || player_id.size()>=slot->player_id.size()) return false;
    if (slot->attached) { copy_text(slot->player_id,player_id); return true; }
#if defined(__linux__)
    const auto handle=::open(slot->descriptor.path.data(),O_RDONLY|O_NONBLOCK|O_CLOEXEC); if (handle<0) return false;
    slot->handle=handle;
#elif defined(_WIN32) || defined(__APPLE__)
    const auto native_hash=native_hash_from_identity(slot->descriptor.path.data()); if (native_hash.empty()) return false;
    auto native=std::unique_ptr<NativeMidiInput>(new (std::nothrow) NativeMidiInput()); if (!native || !native->attach(native_hash)) return false;
    slot->native=std::move(native); slot->native_drops_seen=slot->native->dropped_bytes();
#else
    return false;
#endif
    slot->attached=true; copy_text(slot->player_id,player_id); slot->parser.reset(); return true;
}

bool MidiInputManager::detach(std::string_view device_id) noexcept { auto* slot=find_slot(device_id); if (!slot) return false; close_slot(*slot); return true; }
std::size_t MidiInputManager::attached_count() const noexcept { std::size_t n=0; for(std::size_t i=0;i<device_count_;++i) if(devices_[i].attached) ++n; return n; }

bool MidiInputManager::queue(const CapturedMidiInput& event) noexcept {
    if(queue_size_>=queue_capacity){audit_queue_drops_.fetch_add(1,std::memory_order_relaxed);return false;}
    queue_[queue_head_]=event; queue_head_=(queue_head_+1)%queue_capacity; ++queue_size_; return true;
}
bool MidiInputManager::pop(CapturedMidiInput& out) noexcept { if(!queue_size_) return false; out=queue_[queue_tail_]; queue_tail_=(queue_tail_+1)%queue_capacity; --queue_size_; return true; }
bool MidiInputManager::inject(std::string_view device_id,std::string_view player_id,const MidiInputMessage& message) noexcept {
    if(device_id.empty()||player_id.empty()||device_id.size()>=64||player_id.size()>=64)return false;
    CapturedMidiInput event{}; copy_text(event.device_id,device_id); copy_text(event.player_id,player_id); event.message=message;
    const auto accepted=queue(event); if(accepted){audit_injected_.fetch_add(1,std::memory_order_relaxed);audit_messages_.fetch_add(1,std::memory_order_relaxed);} return accepted;
}

std::size_t MidiInputManager::poll(std::uint64_t show_time_ns) noexcept {
    const auto started=std::chrono::steady_clock::now(); audit_polls_.fetch_add(1,std::memory_order_relaxed); std::size_t captured=0;
    std::array<std::uint8_t,256> bytes{};
    for(std::size_t i=0;i<device_count_;++i){
        auto& slot=devices_[i]; if(!slot.attached) continue;
#if defined(__linux__)
        if(slot.handle<0) continue;
        for(;;){ const auto read_count=::read(slot.handle,bytes.data(),bytes.size()); if(read_count<=0) break;
            audit_bytes_.fetch_add(static_cast<std::uint64_t>(read_count),std::memory_order_relaxed);
            for(ssize_t index=0;index<read_count;++index){ MidiInputMessage parsed{}; if(!slot.parser.feed(bytes[static_cast<std::size_t>(index)],show_time_ns,parsed))continue;
                CapturedMidiInput event{}; event.device_id=slot.descriptor.id; event.player_id=slot.player_id; event.message=parsed;
                if(queue(event)){++captured;audit_messages_.fetch_add(1,std::memory_order_relaxed);}
            }
        }
#elif defined(_WIN32) || defined(__APPLE__)
        if(!slot.native || !slot.native->attached()){ close_slot(slot); continue; }
        for(;;){ const auto count=slot.native->poll_bytes(bytes.data(),bytes.size()); if(!count) break;
            audit_bytes_.fetch_add(count,std::memory_order_relaxed);
            for(std::size_t index=0;index<count;++index){ MidiInputMessage parsed{}; if(!slot.parser.feed(bytes[index],show_time_ns,parsed))continue;
                CapturedMidiInput event{}; event.device_id=slot.descriptor.id; event.player_id=slot.player_id; event.message=parsed;
                if(queue(event)){++captured;audit_messages_.fetch_add(1,std::memory_order_relaxed);}
            }
        }
        const auto drops=slot.native->dropped_bytes(); if(drops>slot.native_drops_seen){audit_queue_drops_.fetch_add(drops-slot.native_drops_seen,std::memory_order_relaxed);slot.native_drops_seen=drops;}
#endif
    }
    const auto duration=static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-started).count());
    auto maximum=audit_max_poll_ns_.load(std::memory_order_relaxed); while(duration>maximum&&!audit_max_poll_ns_.compare_exchange_weak(maximum,duration,std::memory_order_relaxed)){}
    return captured;
}

MidiIngressAuditStatus MidiInputManager::audit_status() const noexcept {
    return {audit_polls_.load(std::memory_order_relaxed),audit_bytes_.load(std::memory_order_relaxed),audit_messages_.load(std::memory_order_relaxed),audit_queue_drops_.load(std::memory_order_relaxed),audit_injected_.load(std::memory_order_relaxed),audit_max_poll_ns_.load(std::memory_order_relaxed),false};
}
} // namespace stageforge
