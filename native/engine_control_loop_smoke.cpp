#include "engine_control_loop.h"

#include <array>
#include <cstddef>
#include <iostream>

namespace {

struct Context {
    std::array<stageforge::EngineControlWaitResult, 4> waits{
        stageforge::EngineControlWaitResult::timeout,
        stageforge::EngineControlWaitResult::timeout,
        stageforge::EngineControlWaitResult::ready,
        stageforge::EngineControlWaitResult::closed,
    };
    std::size_t next_wait{0};
    std::uint32_t observed_interval{0};
    unsigned int services{0};
    unsigned int reads{0};
    unsigned int dispatches{0};
};

stageforge::EngineControlWaitResult wait(void* raw, std::uint32_t interval) noexcept {
    auto& context = *static_cast<Context*>(raw);
    context.observed_interval = interval;
    if (context.next_wait >= context.waits.size()) return stageforge::EngineControlWaitResult::closed;
    return context.waits[context.next_wait++];
}

bool read(void* raw) noexcept {
    ++static_cast<Context*>(raw)->reads;
    return true;
}

void service(void* raw) noexcept {
    ++static_cast<Context*>(raw)->services;
}

bool dispatch(void* raw) noexcept {
    ++static_cast<Context*>(raw)->dispatches;
    return true;
}

} // namespace

int main() {
    Context context{};
    const stageforge::EngineControlLoopCallbacks callbacks{wait, read, service, dispatch, &context};
    if (!stageforge::run_engine_control_loop(callbacks, 17)) return 1;
    if (context.observed_interval != 17 || context.services != 4 || context.reads != 1 || context.dispatches != 1) return 2;

    const stageforge::EngineControlLoopCallbacks invalid{};
    if (stageforge::run_engine_control_loop(invalid, 17)) return 3;
    if (stageforge::run_engine_control_loop(callbacks, 0)) return 4;

    std::cout << "engine control loop smoke passed\n";
    return 0;
}
