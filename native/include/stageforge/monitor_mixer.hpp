#pragma once

#include <cstddef>
#include <span>

#include "stageforge/monitor_bus.hpp"

namespace stageforge {

struct MonitorSourceBlock {
    MonitorChannel channel{};
    const float* samples{nullptr};
};

class MonitorMixer {
public:
    // Mixes mono source stems into a personal stereo bus. No allocation, locks,
    // device I/O, or limiter work happens here. Callers provide all buffers.
    static void mix(
        const MonitorBus& bus,
        std::span<const MonitorSourceBlock> sources,
        float* output_left,
        float* output_right,
        std::size_t frames) noexcept;

private:
    [[nodiscard]] static float gain(float percent) noexcept;
};

} // namespace stageforge
