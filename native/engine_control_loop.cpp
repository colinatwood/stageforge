#include "engine_control_loop.h"

namespace stageforge {

bool run_engine_control_loop(const EngineControlLoopCallbacks& callbacks,
                             std::uint32_t service_interval_ms) noexcept {
    if (!callbacks.wait || !callbacks.read || !callbacks.service ||
        !callbacks.dispatch || service_interval_ms == 0) {
        return false;
    }

    for (;;) {
        const auto wait_result = callbacks.wait(callbacks.context, service_interval_ms);

        // Service first after every bounded wait. This intentionally keeps the
        // native stream owner, topology reconciliation, and command dispatch on
        // the same thread rather than inventing a second owner thread.
        callbacks.service(callbacks.context);

        if (wait_result == EngineControlWaitResult::timeout) {
            continue;
        }
        if (wait_result == EngineControlWaitResult::closed) {
            return true;
        }
        if (wait_result == EngineControlWaitResult::failed) {
            return false;
        }
        if (!callbacks.read(callbacks.context)) {
            return true;
        }
        if (!callbacks.dispatch(callbacks.context)) {
            return true;
        }
    }
}

} // namespace stageforge
