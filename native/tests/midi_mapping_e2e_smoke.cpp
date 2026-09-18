#include "stageforge/midi_input.hpp"
#include "stageforge/midi_learn_router.hpp"
#include "stageforge/midi_mapped_action_dispatcher.hpp"
#include "stageforge/show_execution_loop.hpp"
#include "stageforge/transport_clock.hpp"

#include <cstdio>
#include <cstdlib>
#include <string_view>

#define SF_CHECK(expr) do { if (!(expr)) { std::fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); std::abort(); } } while (false)

namespace {
std::uint64_t stable_token_id(std::string_view value) noexcept {
    std::uint64_t hash = 14695981039346656037ULL;
    for (const unsigned char byte : value) { hash ^= byte; hash *= 1099511628211ULL; }
    return hash ? hash : 1;
}

struct Sink { stageforge::ShowEvent event{}; std::size_t count{0}; };
bool capture(void* raw, const stageforge::ShowEvent& event, bool) noexcept {
    auto& sink = *static_cast<Sink*>(raw);
    sink.event = event;
    ++sink.count;
    return true;
}
bool submit_to_loop(void* raw, const stageforge::ShowEvent& event) noexcept {
    auto* loop = static_cast<stageforge::ShowExecutionLoop<8, 8>*>(raw);
    return loop && loop->submit(event);
}
}

int main() {
    constexpr std::string_view device = "hosted:midi:e2e";
    stageforge::MidiInputManager manager;
    stageforge::MidiLearnRouter<4, 4> router;
    stageforge::MidiLearnBinding binding{};
    binding.mapping_id = 1;
    binding.device_id = stable_token_id(device);
    binding.target_id = 42;
    binding.parameter_id = 7;
    binding.channel = 0;
    binding.number = 74;
    binding.message = stageforge::MidiLearnMessage::control_change;
    binding.behavior = stageforge::MidiMapBehavior::absolute;
    binding.minimum = 0.0F;
    binding.maximum = 1.0F;
    SF_CHECK(router.upsert(binding));

    stageforge::TransportClock clock(48000.0, 120.0);
    Sink sink{};
    stageforge::ShowExecutionLoop<8, 8> loop(clock, &capture, &sink);
    stageforge::MidiMappedActionDispatcher dispatcher(&submit_to_loop, &loop, 99);

    const stageforge::MidiInputMessage message{0, 0xB0, 74, 127};
    SF_CHECK(manager.inject(device, "hosted-player", message));
    stageforge::CapturedMidiInput input{};
    SF_CHECK(manager.pop(input));
    router.process(stable_token_id(input.device_id.data()), input.message.status,
                   input.message.data1, input.message.data2, input.message.show_time_ns);
    stageforge::MidiMappedAction action{};
    SF_CHECK(router.pop(action));
    SF_CHECK(dispatcher.dispatch(action, 12));
    SF_CHECK(loop.drain_until(0) == 1);

    SF_CHECK(sink.count == 1);
    SF_CHECK(sink.event.type == stageforge::ShowEventType::automation);
    SF_CHECK(sink.event.owner_id == 99);
    SF_CHECK(sink.event.revision == 12);
    SF_CHECK(sink.event.payload.automation.target_id == 42);
    SF_CHECK(sink.event.payload.automation.parameter_id == 7);
    SF_CHECK(sink.event.payload.automation.value == 1.0F);
    SF_CHECK((sink.event.flags & stageforge::show_event_authoritative) != 0);
    SF_CHECK(!manager.audit_status().physical_outputs_armed);
    SF_CHECK(!router.status().physical_outputs_armed);
    SF_CHECK(!dispatcher.status().physical_outputs_armed);
    return 0;
}
