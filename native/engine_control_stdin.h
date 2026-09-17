#pragma once

#include "engine_control_loop.h"

#include <cstdint>

namespace stageforge {

// Bounded readiness wait for the engine's stdin command channel. This does not
// read bytes; the existing command parser remains the sole consumer. The wait
// is intentionally bounded so the owner thread can service native endpoint
// topology even when the controller is idle.
EngineControlWaitResult wait_engine_stdin(std::uint32_t timeout_ms) noexcept;

} // namespace stageforge
