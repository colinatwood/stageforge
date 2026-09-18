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
#if defined(_WIN32) || defined(__APPLE__)
void NativeMidiInputDeleter::operator()(NativeMidiInput* input) const noexcept { delete input; }
#endif
namespace {
template <std::size_t N> void copy_text(std::array<char,N>& target,std::string_view source) noexcept { const auto count=std::min(source.size(),N-1);std::memcpy(target.data(),source.data(),count);target[count]='\0'; }
#if defined(__linux__)
bool is_midi_path(const char* name) noexcept{return name&&std::strncmp(name,"midiC",5)==0&&std::strchr(name,'D')!=nullptr;}
std::string midi_id_from_path(std::string_view path){return "alsa:"+std::string(path);}
#elif defined(_WIN32) || defined(__APPLE__)
constexpr std::size_t max_native_bytes_per_device_poll=8192;
std::string target_midi_identity(const DeviceRecord& record,std::string_view backend){return std::string(backend)+":hash:"+record.native_hash;}
std::string target_midi_id(const DeviceRecord& record,std::string_view backend){return "midi:"+target_midi_identity(record,backend);}
std::string_view native_hash_from_identity(std::string_view identity) noexcept{const auto marker=identity.find(":hash:");if(marker==std::string_view::npos)return {};return identity.substr(marker+6);}
#endif
}
std::uint8_t MidiByteParser::data_length(std::uint8_t status) noexcept{if(status<0x80)return 0;if(status<0xF0){const auto type=status&0xF0;return(type==0xC0||type==0xD0)?1:2;}switch(status){case 0xF1:case 0xF3:return 1;case 0xF2:return 2;default:return 0;}}
void MidiByteParser::reset() noexcept{running_status_=message_status_=expected_=received_=0;data_={};in_sysex_=false;}
bool MidiByteParser::feed(std::uint8_t byte,std::uint64_t show_time_ns,MidiInputMessage& out) noexcept{if(byte>=0xF8)return false;if(in_sysex_){if(byte==0xF7)in_sysex_=false;return false;}if(byte&0x80){if(byte==0xF0){in_sysex_=true;running_status_=message_status_=expected_=received_=0;return false;}if(byte==0xF7)return false;message_status_=byte;expected_=data_length(byte);received_=0;running_status_=(byte<0xF0)?byte:0;if(expected_==0){out={show_time_ns,byte,0,0};return true;}return false;}if(expected_==0){if(running_status_==0)return false;message_status_=running_status_;expected_=data_length(running_status_);received_=0;}if(received_<data_.size())data_[received_]=byte;++received_;if(received_<expected_)return false;out={show_time_ns,message_status_,data_[0],expected_>1?data_[1]:std::uint8_t{0}};received_=0;if(message_status_>=0xF0){expected_=0;message_status_=0;}return true;}
MidiInputManager::MidiInputManager() noexcept{(void)scan();}
MidiInputManager::~MidiInputManager(){for(std::size_t i=0;i<device_count_;++i)close_slot(devices_[i]);}
const MidiDeviceDescriptor* MidiInputManager::device(std::size_t i) const noexcept{return i<device_count_?&devices_[i].descriptor:nullptr;}
MidiInputManager::DeviceSlot* MidiInputManager::find_slot(std::string_view id) noexcept{for(std::size_t i=0;i<device_count_;++i)if(id==devices_[i].descriptor.id.data())return &devices_[i];return nullptr;}
const MidiInputManager::DeviceSlot* MidiInputManager::find_slot(std::string_view id) const noexcept{for(std::size_t i=0;i<device_count_;++i)if(id==devices_[i].descriptor.id.data())return &devices_[i];return nullptr;}
bool MidiInputManager::attached(std::string_view id) const noexcept{auto* s=find_slot(id);return s&&s->attached;}
void MidiInputManager::close_slot(DeviceSlot& slot) noexcept{
#if defined(__linux__)
if(slot.handle>=0)::close(slot.handle);
#elif defined(_WIN32) || defined(__APPLE__)
if(slot.native)slot.native->detach();slot.native.reset();slot.native_drops_seen=0;
#endif
slot.handle=-1;slot.attached=false;slot.player_id[0]='\0';slot.parser.reset();}
#if defined(_WIN32) || defined(__APPLE__)
void MidiInputManager::purge_queued_device(std::string_view device_id) noexcept{const auto queued_before=queue_size_;for(std::size_t i=0;i<queued_before;++i){CapturedMidiInput event{};(void)pop(event);if(midi_event_survives_detach(device_id,event.device_id.data()))(void)queue(event);}}
#endif
std::size_t MidiInputManager::scan() noexcept{std::array<DeviceSlot,max_devices> found{};std::size_t found_count=0;
#if defined(__linux__)
DIR* dir=::opendir("/dev/snd");if(dir){while(auto* entry=::readdir(dir)){if(found_count>=max_devices)break;if(!is_midi_path(entry->d_name))continue;auto& slot=found[found_count++];std::string path="/dev/snd/";path+=entry->d_name;copy_text(slot.descriptor.path,path);copy_text(slot.descriptor.id,midi_id_from_path(path));copy_text(slot.descriptor.name,entry->d_name);slot.descriptor.connected=true;slot.descriptor.input=true;if(auto* existing=find_slot(slot.descriptor.id.data());existing&&existing->attached){slot.handle=existing->handle;existing->handle=-1;slot.attached=true;slot.player_id=existing->player_id;slot.parser=existing->parser;}}::closedir(dir);}
#elif defined(_WIN32) || defined(__APPLE__)
try{DeviceMonitor monitor;monitor.start();const auto snapshot=monitor.snapshot();monitor.stop();
#if defined(_WIN32)
constexpr std::string_view backend="winmm";
#else
constexpr std::string_view backend="coremidi";
#endif
for(const auto& record:snapshot.devices){if(found_count>=max_devices)break;if(record.kind!=DeviceKind::Midi||!record.input||record.native_hash.empty())continue;auto& slot=found[found_count++];const auto id=target_midi_id(record,backend);copy_text(slot.descriptor.id,id);copy_text(slot.descriptor.path,target_midi_identity(record,backend));
#if defined(_WIN32)
copy_text(slot.descriptor.name,"Windows MIDI Endpoint");
#else
copy_text(slot.descriptor.name,"CoreMIDI Endpoint");
#endif
slot.descriptor.connected=true;slot.descriptor.input=true;if(auto* existing=find_slot(id);existing&&existing->attached){slot.native=std::move(existing->native);slot.native_drops_seen=existing->native_drops_seen;slot.attached=slot.native&&slot.native->attached();slot.player_id=existing->player_id;slot.parser=existing->parser;}}}catch(...){found_count=0;}
#endif
for(std::size_t i=0;i<device_count_;++i)close_slot(devices_[i]);devices_=std::move(found);device_count_=found_count;
#if defined(_WIN32) || defined(__APPLE__)
const auto queued_before_scan=queue_size_;for(std::size_t i=0;i<queued_before_scan;++i){CapturedMidiInput event{};(void)pop(event);if(find_slot(event.device_id.data())!=nullptr)(void)queue(event);}
#endif
return device_count_;}
bool MidiInputManager::attach(std::string_view device_id,std::string_view player_id) noexcept{auto* slot=find_slot(device_id);if(!slot||player_id.empty()||player_id.size()>=slot->player_id.size())return false;if(slot->attached){if(midi_attachment_owner_matches(slot->player_id.data(),player_id))return true;return false;}
#if defined(__linux__)
const auto handle=::open(slot->descriptor.path.data(),O_RDONLY|O_NONBLOCK|O_CLOEXEC);if(handle<0)return false;slot->handle=handle;
#elif defined(_WIN32) || defined(__APPLE__)
const auto native_hash=native_hash_from_identity(slot->descriptor.path.data());if(native_hash.empty())return false;std::unique_ptr<NativeMidiInput,NativeMidiInputDeleter> native(new(std::nothrow)NativeMidiInput());if(!native||!native->attach(native_hash))return false;slot->native=std::move(native);slot->native_drops_seen=slot->native->dropped_bytes();
#else
return false;
#endif
slot->attached=true;copy_text(slot->player_id,player_id);slot->parser.reset();return true;}
bool MidiInputManager::detach(std::string_view device_id) noexcept{auto* slot=find_slot(device_id);if(!slot)return false;close_slot(*slot);
#if defined(_WIN32) || defined(__APPLE__)
purge_queued_device(device_id);
#endif
return true;}
std::size_t MidiInputManager::attached_count() const noexcept{std::size_t n=0;for(std::size_t i=0;i<device_count_;++i)if(devices_[i].attached)++n;return n;}
bool MidiInputManager::queue(const CapturedMidiInput& event) noexcept{if(queue_size_>=queue_capacity){audit_queue_drops_.fetch_add(1,std::memory_order_relaxed);return false;}queue_[queue_head_]=event;queue_head_=(queue_head_+1)%queue_capacity;++queue_size_;return true;}
bool MidiInputManager::pop(CapturedMidiInput& out) noexcept{if(!queue_size_)return false;out=queue_[queue_tail_];queue_tail_=(queue_tail_+1)%queue_capacity;--queue_size_;return true;}
bool MidiInputManager::inject(std::string_view device_id,std::string_view player_id,const MidiInputMessage& message) noexcept{CapturedMidiInput event{};if(device_id.empty()||player_id.empty()||device_id.size()>=event.device_id.size()||player_id.size()>=event.player_id.size())return false;copy_text(event.device_id,device_id);copy_text(event.player_id,player_id);event.message=message;const auto accepted=queue(event);if(accepted){audit_injected_.fetch_add(1,std::memory_order_relaxed);audit_messages_.fetch_add(1,std::memory_order_relaxed);}return accepted;}
std::size_t MidiInputManager::poll(std::uint64_t show_time_ns) noexcept{const auto started=std::chrono::steady_clock::now();audit_polls_.fetch_add(1,std::memory_order_relaxed);std::size_t captured=0;std::array<std::uint8_t,256> bytes{};for(std::size_t i=0;i<device_count_;++i){auto& slot=devices_[i];if(!slot.attached)continue;
#if defined(__linux__)
if(slot.handle<0)continue;for(;;){const auto read_count=::read(slot.handle,bytes.data(),bytes.size());if(read_count<=0)break;audit_bytes_.fetch_add(static_cast<std::uint64_t>(read_count),std::memory_order_relaxed);for(ssize_t index=0;index<read_count;++index){MidiInputMessage parsed{};if(!slot.parser.feed(bytes[static_cast<std::size_t>(index)],show_time_ns,parsed))continue;CapturedMidiInput event{};event.device_id=slot.descriptor.id;event.player_id=slot.player_id;event.message=parsed;if(queue(event)){++captured;audit_messages_.fetch_add(1,std::memory_order_relaxed);}}}
#elif defined(_WIN32) || defined(__APPLE__)
if(!slot.native||!slot.native->attached()){const auto revoked_id=std::string(slot.descriptor.id.data());close_slot(slot);purge_queued_device(revoked_id);continue;}std::size_t native_bytes_polled=0;bool overflowed=false;while(native_bytes_polled<max_native_bytes_per_device_poll){const auto remaining=max_native_bytes_per_device_poll-native_bytes_polled;const auto request=std::min(bytes.size(),remaining);const auto count=slot.native->poll_bytes(bytes.data(),request);if(!slot.native->attached()){const auto revoked_id=std::string(slot.descriptor.id.data());close_slot(slot);purge_queued_device(revoked_id);break;}if(!count)break;native_bytes_polled+=count;audit_bytes_.fetch_add(count,std::memory_order_relaxed);const auto drops=slot.native->dropped_bytes();if(drops>slot.native_drops_seen){audit_queue_drops_.fetch_add(drops-slot.native_drops_seen,std::memory_order_relaxed);slot.native_drops_seen=drops;slot.parser.reset();overflowed=true;}if(overflowed)continue;for(std::size_t index=0;index<count;++index){MidiInputMessage parsed{};if(!slot.parser.feed(bytes[index],show_time_ns,parsed))continue;CapturedMidiInput event{};event.device_id=slot.descriptor.id;event.player_id=slot.player_id;event.message=parsed;if(queue(event)){++captured;audit_messages_.fetch_add(1,std::memory_order_relaxed);}}}if(!slot.attached)continue;const auto drops=slot.native->dropped_bytes();if(drops>slot.native_drops_seen){audit_queue_drops_.fetch_add(drops-slot.native_drops_seen,std::memory_order_relaxed);slot.native_drops_seen=drops;slot.parser.reset();}
#endif
}const auto duration=static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-started).count());auto maximum=audit_max_poll_ns_.load(std::memory_order_relaxed);while(duration>maximum&&!audit_max_poll_ns_.compare_exchange_weak(maximum,duration,std::memory_order_relaxed)){}return captured;}
MidiIngressAuditStatus MidiInputManager::audit_status() const noexcept{return{audit_polls_.load(std::memory_order_relaxed),audit_bytes_.load(std::memory_order_relaxed),audit_messages_.load(std::memory_order_relaxed),audit_queue_drops_.load(std::memory_order_relaxed),audit_injected_.load(std::memory_order_relaxed),audit_max_poll_ns_.load(std::memory_order_relaxed),false};}
} // namespace stageforge