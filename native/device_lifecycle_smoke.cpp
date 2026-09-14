#include "device_monitor.h"
#include "device_identity.h"
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <set>

int main() {
    try {
        if (stageforge::identity_hash("coreaudio-uid-v1", "stageforge-fixture") !=
            "sha256:6d82db5132fccf333e0d45ea337ee34bf7b1ed11aaa83603e3a12090deb4bbf9")
            throw std::runtime_error("native identity hash differs from independent SHA256 vector");
        if (stageforge::identity_hash("windows-endpoint-v1", "stageforge-fixture") ==
            stageforge::identity_hash("coreaudio-uid-v1", "stageforge-fixture"))
            throw std::runtime_error("identity domain separation failed");
        bool empty_rejected = false;
        try { stageforge::identity_hash("coreaudio-uid-v1", ""); }
        catch (const std::invalid_argument&) { empty_rejected = true; }
        if (!empty_rejected) throw std::runtime_error("empty identity accepted");
        stageforge::DeviceMonitor monitor;
        bool rejected = false;
        try { monitor.snapshot(); } catch (const std::logic_error&) { rejected = true; }
        if (!rejected) throw std::runtime_error("inactive snapshot accepted");
        stageforge::DeviceSnapshot snapshot{};
        auto begin = std::chrono::steady_clock::now();
        for (unsigned cycle = 0; cycle < 25; ++cycle) {
            monitor.start(); monitor.start();
            snapshot = monitor.snapshot();
            if (snapshot.identities.size() != snapshot.device_count)
                throw std::runtime_error("device identity count mismatch");
            std::set<std::string> identities;
            for (const auto& identity : snapshot.identities) {
                if (identity.hash.size() != 71 || identity.hash.substr(0, 7) != "sha256:" || !identities.insert(identity.hash).second)
                    throw std::runtime_error("malformed or duplicate identity");
#ifdef _WIN32
                if (identity.scope != stageforge::DeviceIdentity::Scope::WindowsEndpoint)
#else
                if (identity.scope != stageforge::DeviceIdentity::Scope::CoreAudioUID)
#endif
                    throw std::runtime_error("unexpected identity scope");
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
            monitor.stop(); monitor.stop();
        }
        bool wrong_thread_rejected = false;
        std::thread other([&] {
            try { monitor.start(); } catch (const std::logic_error&) { wrong_thread_rejected = true; }
        });
        other.join();
        if (!wrong_thread_rejected) throw std::runtime_error("cross-thread start accepted");
        // Exercise active destruction as well as explicit stop/restart.
        { stageforge::DeviceMonitor another; another.start(); another.snapshot(); }
        auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
        std::cout << std::boolalpha << "{\"cycles\":25,\"activeDestructionPassed\":true,"
            << "\"inactiveSnapshotRejected\":true,\"wrongThreadRejected\":true,\"deviceCount\":" << snapshot.device_count
            << ",\"defaultInputPresent\":" << snapshot.default_input_present
            << ",\"defaultOutputPresent\":" << snapshot.default_output_present
            << ",\"observedNotificationRevision\":" << monitor.revision()
            << ",\"identityCount\":" << snapshot.identities.size()
            << ",\"identityHashContractPassed\":true"
            << ",\"elapsedSeconds\":" << elapsed << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
