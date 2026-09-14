#include "device_monitor.h"
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>

int main() {
    try {
        stageforge::DeviceMonitor monitor;
        bool rejected = false;
        try { monitor.snapshot(); } catch (const std::logic_error&) { rejected = true; }
        if (!rejected) throw std::runtime_error("inactive snapshot accepted");
        stageforge::DeviceSnapshot snapshot{};
        auto begin = std::chrono::steady_clock::now();
        for (unsigned cycle = 0; cycle < 25; ++cycle) {
            monitor.start(); monitor.start();
            snapshot = monitor.snapshot();
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
            << ",\"elapsedSeconds\":" << elapsed << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
