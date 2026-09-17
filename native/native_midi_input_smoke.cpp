#include "native_midi_input.h"

#include <array>
#include <cassert>
#include <cstdint>

int main() {
    stageforge::NativeMidiInput input;
    assert(!input.attached());
    assert(!input.attach("not-a-hash"));
    assert(!input.attached());
    assert(!input.attach("sha256:0000000000000000000000000000000000000000000000000000000000000000"));
    assert(!input.attached());
    std::array<std::uint8_t, 16> bytes{};
    assert(input.poll_bytes(bytes.data(), bytes.size()) == 0);
    input.detach();
    assert(!input.attached());
    return 0;
}
