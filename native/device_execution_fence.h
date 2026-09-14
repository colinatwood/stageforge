#pragma once
#include "device_identity.h"
#include <cstdint>
#include <vector>

namespace stageforge {

enum class ExecutionFenceState {
    Unarmed,
    Armed,
    FencedDetached,
    FencedAmbiguous,
    RecoveredDisarmed,
};

struct FenceObservation {
    ExecutionFenceState state = ExecutionFenceState::Unarmed;
    ResolutionStatus resolution = ResolutionStatus::Detached;
    bool execution_allowed = false;
    bool explicit_rearm_required = true;
    std::uint64_t generation = 0;
};

// Control-thread safety state machine. This class never opens, starts, stops, or
// rearms a stream by itself. A caller that owns a physical stream must stop/fence
// it immediately whenever execution_allowed becomes false.
class DeviceExecutionFence {
public:
    explicit DeviceExecutionFence(DeviceSelection selection);

    const DeviceSelection& selection() const noexcept { return selection_; }
    FenceObservation observation() const noexcept;

    // Initial arming requires the originally selected native object to still be
    // attached. A replacement identity cannot silently turn an unarmed fence on.
    bool arm_initial(const std::vector<DeviceRecord>& devices);

    // Reconcile one control-thread snapshot. Any detach/ambiguity disarms.
    // Exact-unique strong recovery updates the selected native identity but stays
    // disarmed until explicit_rearm() succeeds.
    FenceObservation reconcile(const std::vector<DeviceRecord>& devices);

    // Explicit operator/control-plane recovery gate. Attached or exact-unique
    // strong rebound may arm; detached/ambiguous states fail closed.
    bool explicit_rearm(const std::vector<DeviceRecord>& devices);

    void disarm() noexcept;

private:
    void transition(ExecutionFenceState next, ResolutionStatus resolution) noexcept;
    void accept_resolved_native(const DeviceRecord& record);

    DeviceSelection selection_;
    ExecutionFenceState state_ = ExecutionFenceState::Unarmed;
    ResolutionStatus resolution_ = ResolutionStatus::Detached;
    std::uint64_t generation_ = 0;
};

const char* execution_fence_state_name(ExecutionFenceState state);

}
