#include "stageforge/midi_input.hpp"

#include <cstdio>
#include <cstdlib>
#include <string_view>

#define SF_CHECK(expr) do { \
    if (!(expr)) { \
        std::fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); \
        std::abort(); \
    } \
} while (false)

int main() {
    stageforge::MidiInputManager manager;

    const stageforge::MidiInputMessage injected{123456789ULL, 0x90, 60, 100};
    SF_CHECK(manager.inject("hosted:midi", "hosted-player", injected));
    SF_CHECK(manager.queued() == 1);

    stageforge::CapturedMidiInput captured{};
    SF_CHECK(manager.pop(captured));
    SF_CHECK(std::string_view(captured.device_id.data()) == "hosted:midi");
    SF_CHECK(std::string_view(captured.player_id.data()) == "hosted-player");
    SF_CHECK(captured.message.show_time_ns == injected.show_time_ns);
    SF_CHECK(captured.message.status == injected.status);
    SF_CHECK(captured.message.data1 == injected.data1);
    SF_CHECK(captured.message.data2 == injected.data2);
    SF_CHECK(manager.queued() == 0);
    SF_CHECK(!manager.pop(captured));

    const auto ingress_audit = manager.audit_status();
    SF_CHECK(ingress_audit.injected_messages == 1);
    SF_CHECK(ingress_audit.messages == 1);
    SF_CHECK(!ingress_audit.physical_outputs_armed);

#if defined(_WIN32) || defined(__APPLE__)
    (void)manager.scan();

#if defined(_WIN32)
    constexpr std::string_view id_prefix = "midi:winmm:hash:sha256:";
    constexpr std::string_view path_prefix = "winmm:hash:sha256:";
#else
    constexpr std::string_view id_prefix = "midi:coremidi:hash:sha256:";
    constexpr std::string_view path_prefix = "coremidi:hash:sha256:";
#endif
    for (std::size_t i = 0; i < manager.device_count(); ++i) {
        const auto* descriptor = manager.device(i);
        SF_CHECK(descriptor != nullptr);
        const std::string_view id(descriptor->id.data());
        const std::string_view path(descriptor->path.data());
        SF_CHECK(id.starts_with(id_prefix));
        SF_CHECK(path.starts_with(path_prefix));
        SF_CHECK(id.size() == id_prefix.size() + 64);
        SF_CHECK(path.size() == path_prefix.size() + 64);
        SF_CHECK(id.find(":name:") == std::string_view::npos);
        SF_CHECK(id.find(":index:") == std::string_view::npos);
    }

    // Use a complete target-OS-shaped identity. This specifically guards against
    // regressing to the former 64-byte storage limit that truncated SHA-256 IDs.
#if defined(_WIN32)
    constexpr auto stale_id = "midi:winmm:hash:sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
#else
    constexpr auto stale_id = "midi:coremidi:hash:sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
#endif
    SF_CHECK(manager.inject(stale_id, "revoked-player", injected));
    SF_CHECK(manager.queued() == 1);
    (void)manager.scan();
    SF_CHECK(manager.queued() == 0);
    SF_CHECK(!manager.pop(captured));

    constexpr auto missing = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
    SF_CHECK(!manager.attach(missing, "hosted-safe-test"));
    SF_CHECK(!manager.attached(missing));
    SF_CHECK(manager.attached_count() == 0);
    SF_CHECK(!manager.detach(missing));

    const auto audit = manager.audit_status();
    SF_CHECK(!audit.physical_outputs_armed);
#endif
    return 0;
}
