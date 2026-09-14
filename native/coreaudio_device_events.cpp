#include "device_monitor.h"
#include "device_identity.h"
#include <CoreAudio/CoreAudio.h>
#include <CoreFoundation/CoreFoundation.h>
#include <algorithm>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <unistd.h>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
class Aggregate {
    AudioDeviceID id_ = kAudioObjectUnknown;
public:
    explicit Aggregate(const std::string& uid) {
        CFStringRef value = CFStringCreateWithCString(nullptr, uid.c_str(), kCFStringEncodingUTF8);
        require(value != nullptr, "fixture UID creation failed");
        const void* keys[] = {CFSTR(kAudioAggregateDeviceNameKey), CFSTR(kAudioAggregateDeviceUIDKey), CFSTR(kAudioAggregateDeviceIsPrivateKey)};
        const void* values[] = {CFSTR("StageForge CI empty aggregate"), value, kCFBooleanTrue};
        auto description = CFDictionaryCreate(nullptr, keys, values, 3, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
        if (!description) { CFRelease(value); throw std::runtime_error("fixture description failed"); }
        auto status = AudioHardwareCreateAggregateDevice(description, &id_);
        CFRelease(description); CFRelease(value);
        require(status == noErr && id_ != kAudioObjectUnknown, "create empty private aggregate failed");
    }
    Aggregate(const Aggregate&) = delete;
    Aggregate& operator=(const Aggregate&) = delete;
    void close() {
        if (id_ != kAudioObjectUnknown) {
            require(AudioHardwareDestroyAggregateDevice(id_) == noErr, "destroy aggregate failed");
            id_ = kAudioObjectUnknown;
        }
    }
    ~Aggregate() { try { close(); } catch (...) { std::terminate(); } }
};
bool contains(const stageforge::DeviceSnapshot& snapshot, const std::string& hash) {
    return std::count_if(snapshot.identities.begin(), snapshot.identities.end(), [&](const auto& id) {
        return id.scope == stageforge::DeviceIdentity::Scope::CoreAudioUID && id.hash == hash;
    }) == 1;
}
template<class Predicate> void await_condition(Predicate predicate, const char* failure) {
    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(8);
    while (std::chrono::steady_clock::now() < deadline) {
        if (predicate()) return;
        // CoreAudio notifications are delivered by the native listener mechanism.
        // Run-loop service is allowed; the test never calls the callback directly.
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.01, false);
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    throw std::runtime_error(failure);
}
}
int main() {
    try {
        stageforge::DeviceMonitor monitor;
        monitor.start();
        const auto uid = "org.stageforge.ci.empty." + std::to_string(getpid());
        const auto hash = stageforge::identity_hash("coreaudio-uid-v1", uid);
        require(!contains(monitor.snapshot(), hash), "fixture already exists");
        unsigned transitions = 0;
        for (unsigned cycle = 0; cycle < 2; ++cycle) {
            auto before = monitor.revision();
            Aggregate fixture(uid); // No subdevices, I/O callback, tap, or stream.
            await_condition([&] { return monitor.revision() > before && contains(monitor.snapshot(), hash); }, "addition notification/identity missing");
            ++transitions;
            before = monitor.revision();
            fixture.close();
            await_condition([&] { return monitor.revision() > before && !contains(monitor.snapshot(), hash); }, "removal notification/identity missing");
            ++transitions;
            monitor.stop(); monitor.start();
        }
        monitor.stop();
        std::cout << "{\"fixture\":\"private-empty-coreaudio-aggregate\",\"observedTransitions\":" << transitions
            << ",\"sameUidRecreationPassed\":true,\"listenerRestartPassed\":true,\"fixtureCleanupPassed\":true,"
            << "\"nativeNotificationDeliveryPassed\":true,\"physicalHotplugQualified\":false,\"audioStreamingQualified\":false}\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
