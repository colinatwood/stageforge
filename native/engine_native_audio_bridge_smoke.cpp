#include "engine_native_audio_bridge.h"

#include <iostream>
#include <string>

namespace {
std::string hash(char value) { return std::string("sha256:") + std::string(64, value); }
}

int main() {
    stageforge::DeviceSelection selection{};
    const auto strong = std::string("native=") + hash('a') + ";persistent=" + hash('b') +
        ";strength=os-stable-endpoint;auto=1";
    if (!stageforge::EngineNativeAudioBridge::decode_selection(strong, false, true, selection) ||
        selection.kind != stageforge::DeviceKind::Audio || selection.native_hash != hash('a') ||
        selection.persistent_hash != hash('b') || !selection.automatic_reconnect ||
        selection.require_input || !selection.require_output) {
        std::cerr << "strong playback selection decode failed\n";
        return 1;
    }

    const auto installation = std::string("native=") + hash('c') + ";persistent=" + hash('d') +
        ";strength=installation-snapshot;auto=0";
    if (!stageforge::EngineNativeAudioBridge::decode_selection(installation, true, false, selection) ||
        selection.automatic_reconnect || !selection.require_input || selection.require_output) {
        std::cerr << "installation capture selection decode failed\n";
        return 2;
    }

    const auto forged_weak_auto = std::string("native=") + hash('c') + ";persistent=" + hash('d') +
        ";strength=installation-snapshot;auto=1";
    if (stageforge::EngineNativeAudioBridge::decode_selection(forged_weak_auto, true, false, selection)) {
        std::cerr << "weak identity acquired automatic reconnect authority\n";
        return 3;
    }
    if (stageforge::EngineNativeAudioBridge::decode_selection(
            "native=raw-device-id;persistent=raw-device-id;strength=os-stable-endpoint;auto=1",
            false, true, selection)) {
        std::cerr << "raw identity escaped hash-only boundary\n";
        return 4;
    }
    if (stageforge::EngineNativeAudioBridge::decode_selection(
            std::string("native=") + hash('A') + ";persistent=" + hash('b') +
            ";strength=os-stable-endpoint;auto=1", false, true, selection)) {
        std::cerr << "malformed uppercase hash accepted\n";
        return 5;
    }

    std::cout << "engine native audio bridge identity decode smoke passed\n";
    return 0;
}
