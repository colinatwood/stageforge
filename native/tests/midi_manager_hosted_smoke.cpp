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

    // Attachment reuse is an exact player-ownership decision independent of
    // physical endpoint availability, so keep this boundary deterministic in CI.
    SF_CHECK(stageforge::midi_attachment_owner_matches("player-a", "player-a"));
    SF_CHECK(!stageforge::midi_attachment_owner_matches("player-a", "player-b"));
    SF_CHECK(!stageforge::midi_attachment_owner_matches("", "player-a"));
    SF_CHECK(!stageforge::midi_attachment_owner_matches("player-a", ""));

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

    stageforge::MidiByteParser parser;
    stageforge::MidiInputMessage parsed{};
    SF_CHECK(!parser.feed(0x90, 10, parsed));
    SF_CHECK(!parser.feed(60, 10, parsed));
    parser.reset();
    SF_CHECK(!parser.feed(100, 10, parsed));
    SF_CHECK(!parser.feed(61, 10, parsed));
    SF_CHECK(!parser.feed(101, 10, parsed));
    SF_CHECK(!parser.feed(0x90, 11, parsed));
    SF_CHECK(!parser.feed(62, 11, parsed));
    SF_CHECK(parser.feed(102, 11, parsed));
    SF_CHECK(parsed.status == 0x90);
    SF_CHECK(parsed.data1 == 62);
    SF_CHECK(parsed.data2 == 102);

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
    SF_CHECK(!manager.attach(stale_id, "hosted-safe-test"));
    SF_CHECK(!manager.attached(stale_id));
    SF_CHECK(manager.attached_count() == 0);
    SF_CHECK(!manager.detach(stale_id));
    const auto audit = manager.audit_status();
    SF_CHECK(!audit.physical_outputs_armed);
#endif
    return 0;
}
