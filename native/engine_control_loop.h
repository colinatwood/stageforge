#pragma once

#include <cstdint>

namespace stageforge {

enum class EngineControlWaitResult : std::uint8_t {
    ready = 0,
    timeout = 1,
    closed = 2,
    failed = 3,
};

using EngineControlWait = EngineControlWaitResult (*)(void*, std::uint32_t) noexcept;
using EngineControlRead = bool (*)(void*) noexcept;
using EngineControlService = void (*)(void*) noexcept;
using EngineControlDispatch = bool (*)(void*) noexcept;

struct EngineControlLoopCallbacks {
    EngineControlWait wait{nullptr};
    EngineControlRead read{nullptr};
    EngineControlService service{nullptr};
    EngineControlDispatch dispatch{nullptr};
    void* context{nullptr};
};

// Runs command dispatch and lifecycle service on one owner thread. The wait
// callback must return within service_interval_ms so native endpoint topology
// fencing cannot go dormant merely because the command channel is idle.
bool run_engine_control_loop(const EngineControlLoopCallbacks& callbacks,
                             std::uint32_t service_interval_ms = 20) noexcept;

} // namespace stageforge
