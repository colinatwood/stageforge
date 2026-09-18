#include "stageforge/midi_input.hpp"

#include <cstdio>
#include <cstdlib>

#define SF_CHECK(expr) do { \
    if (!(expr)) { \
        std::fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); \
        std::abort(); \
    } \
} while (false)

int main() {
#if defined(_WIN32) || defined(__APPLE__)
    stageforge::MidiInputManager manager;
    (void)manager.scan();

    // Hosted-safe exact-identity fence: a syntactically valid but nonexistent
    // native hash must never fall back to a name, index, or default MIDI input.
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
