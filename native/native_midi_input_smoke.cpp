#include "native_midi_input.h"

#include <array>
#include <cassert>
#include <cstdint>

int main() {
    stageforge::NativeMidiInput input;
    std::array<std::uint8_t, 16> bytes{};

    assert(!input.attached());
    assert(input.dropped_bytes() == 0);
    assert(input.poll_bytes(nullptr, bytes.size()) == 0);
    assert(input.poll_bytes(bytes.data(), 0) == 0);

    // Native ownership accepts only the canonical lowercase SHA-256 token shape.
    // Reject malformed framing before touching OS enumeration APIs.
    assert(!input.attach("not-a-hash"));
    assert(!input.attach("sha256:"));
    assert(!input.attach("sha256:0000"));
    assert(!input.attach("sha256:00000000000000000000000000000000000000000000000000000000000000000"));
    assert(!input.attach("sha256:000000000000000000000000000000000000000000000000000000000000000G"));
    assert(!input.attached());
    assert(input.poll_bytes(bytes.data(), bytes.size()) == 0);

    constexpr auto nonexistent =
        "sha256:0000000000000000000000000000000000000000000000000000000000000000";
    assert(!input.attach(nonexistent));
    assert(!input.attached());
    assert(input.poll_bytes(bytes.data(), bytes.size()) == 0);

    input.detach();
    input.detach();
    assert(!input.attached());
    assert(input.poll_bytes(bytes.data(), bytes.size()) == 0);
    return 0;
}
