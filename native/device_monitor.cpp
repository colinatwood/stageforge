#include "device_monitor.h"
#include "device_identity.h"
#include <atomic>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#include <mmdeviceapi.h>
#include <wrl/client.h>
#else
#include <CoreAudio/CoreAudio.h>
#endif

namespace stageforge {
namespace {
// Process-lifetime callback storage prevents teardown races with OS callbacks.
// Each monitor observes a shared topology revision; it owns its subscription.
std::atomic<std::uint64_t> topology_revision{0};
#ifdef _WIN32
void checked(HRESULT status, const char* operation) {
    if (FAILED(status)) throw std::runtime_error(std::string(operation) + ": " + std::to_string(status));
}
class Notifications final : public IMMNotificationClient {
public:
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid != __uuidof(IUnknown) && iid != __uuidof(IMMNotificationClient)) return E_NOINTERFACE;
        *out = static_cast<IMMNotificationClient*>(this); AddRef(); return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return 2; }
    ULONG STDMETHODCALLTYPE Release() override { return 1; }
    HRESULT STDMETHODCALLTYPE OnDeviceStateChanged(LPCWSTR, DWORD) override { return changed(); }
    HRESULT STDMETHODCALLTYPE OnDeviceAdded(LPCWSTR) override { return changed(); }
    HRESULT STDMETHODCALLTYPE OnDeviceRemoved(LPCWSTR) override { return changed(); }
    HRESULT STDMETHODCALLTYPE OnDefaultDeviceChanged(EDataFlow, ERole, LPCWSTR) override { return changed(); }
    HRESULT STDMETHODCALLTYPE OnPropertyValueChanged(LPCWSTR, const PROPERTYKEY) override { return changed(); }
private:
    HRESULT changed() { topology_revision.fetch_add(1, std::memory_order_relaxed); return S_OK; }
};
Notifications notifications;
#else
void checked(OSStatus status, const char* operation) {
    if (status != noErr) throw std::runtime_error(std::string(operation) + ": " + std::to_string(status));
}
OSStatus changed(AudioObjectID, UInt32, const AudioObjectPropertyAddress*, void*) {
    topology_revision.fetch_add(1, std::memory_order_relaxed); return noErr;
}
const AudioObjectPropertyAddress addresses[] = {
    {kAudioHardwarePropertyDevices, kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain},
    {kAudioHardwarePropertyDefaultInputDevice, kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain},
    {kAudioHardwarePropertyDefaultOutputDevice, kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain},
};
#endif
}

struct DeviceMonitor::Impl {
    std::thread::id owner = std::this_thread::get_id();
    bool active = false;
    void check_thread() const {
        if (owner != std::this_thread::get_id()) throw std::logic_error("DeviceMonitor control thread changed");
    }
#ifdef _WIN32
    Microsoft::WRL::ComPtr<IMMDeviceEnumerator> enumerator;
    Impl() {
        checked(CoInitializeEx(nullptr, COINIT_MULTITHREADED), "CoInitializeEx");
        try {
            checked(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL,
                IID_PPV_ARGS(enumerator.GetAddressOf())), "MMDeviceEnumerator");
        } catch (...) { CoUninitialize(); throw; }
    }
    ~Impl() { enumerator.Reset(); CoUninitialize(); }
#else
    unsigned registered = 0;
#endif
};

DeviceMonitor::DeviceMonitor() : impl_(std::make_unique<Impl>()) {}
DeviceMonitor::~DeviceMonitor() {
    // Never free callback storage while the OS might still invoke it. Failure to
    // unregister is fatal rather than silently claiming successful cleanup.
    try { stop(); } catch (...) { std::terminate(); }
}
void DeviceMonitor::start() {
    impl_->check_thread();
    if (impl_->active) return;
#ifdef _WIN32
    checked(impl_->enumerator->RegisterEndpointNotificationCallback(&notifications), "register notifications");
#else
    try {
        for (; impl_->registered < 3; ++impl_->registered)
            checked(AudioObjectAddPropertyListener(kAudioObjectSystemObject,
                &addresses[impl_->registered], changed, impl_.get()), "add property listener");
    } catch (...) { stop(); throw; }
#endif
    impl_->active = true;
}
void DeviceMonitor::stop() {
    impl_->check_thread();
#ifdef _WIN32
    if (impl_->active)
        checked(impl_->enumerator->UnregisterEndpointNotificationCallback(&notifications), "unregister notifications");
#else
    while (impl_->registered) {
        checked(AudioObjectRemovePropertyListener(kAudioObjectSystemObject,
            &addresses[impl_->registered - 1], changed, impl_.get()), "remove property listener");
        --impl_->registered;
    }
#endif
    impl_->active = false;
}
std::uint64_t DeviceMonitor::revision() const { return topology_revision.load(std::memory_order_relaxed); }
DeviceSnapshot DeviceMonitor::snapshot() const {
    impl_->check_thread();
    if (!impl_->active) throw std::logic_error("snapshot requires an active monitor");
    DeviceSnapshot result{};
#ifdef _WIN32
    Microsoft::WRL::ComPtr<IMMDeviceCollection> devices;
    checked(impl_->enumerator->EnumAudioEndpoints(eAll, DEVICE_STATE_ACTIVE, devices.GetAddressOf()), "enumerate endpoints");
    checked(devices->GetCount(&result.device_count), "endpoint count");
    for (unsigned i = 0; i < result.device_count; ++i) {
        Microsoft::WRL::ComPtr<IMMDevice> device;
        checked(devices->Item(i, device.GetAddressOf()), "endpoint item");
        LPWSTR raw = nullptr;
        checked(device->GetId(&raw), "endpoint ID");
        std::unique_ptr<wchar_t, decltype(&CoTaskMemFree)> id(raw, &CoTaskMemFree);
        int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, raw, -1, nullptr, 0, nullptr, nullptr);
        if (size <= 1) throw std::runtime_error("invalid endpoint identity");
        std::string utf8(size, '\0');
        if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, raw, -1, utf8.data(), size, nullptr, nullptr))
            throw std::runtime_error("endpoint identity conversion failed");
        utf8.pop_back();
        result.identities.push_back({identity_hash("windows-endpoint-v1", utf8), DeviceIdentity::Scope::WindowsEndpoint});
    }
    auto has_default = [&](EDataFlow flow) {
        Microsoft::WRL::ComPtr<IMMDevice> device;
        auto status = impl_->enumerator->GetDefaultAudioEndpoint(flow, eConsole, device.GetAddressOf());
        if (status == HRESULT_FROM_WIN32(ERROR_NOT_FOUND)) return false;
        checked(status, "default endpoint"); return true;
    };
    result.default_input_present = has_default(eCapture);
    result.default_output_present = has_default(eRender);
#else
    // Device topology can grow between size and data reads. Retry that race only;
    // all other OS errors remain visible to callers and CI.
    for (unsigned attempt = 0; ; ++attempt) {
        UInt32 size = 0;
        checked(AudioObjectGetPropertyDataSize(kAudioObjectSystemObject, &addresses[0], 0, nullptr, &size), "device data size");
        std::vector<AudioDeviceID> devices(size / sizeof(AudioDeviceID));
        auto status = size ? AudioObjectGetPropertyData(kAudioObjectSystemObject, &addresses[0], 0, nullptr, &size, devices.data()) : noErr;
        if (status == kAudioHardwareBadPropertySizeError && attempt < 2) continue;
        checked(status, "enumerate devices");
        result.device_count = size / sizeof(AudioDeviceID);
        for (unsigned i = 0; i < result.device_count; ++i) {
            AudioObjectPropertyAddress uid_address{kAudioDevicePropertyDeviceUID, kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain};
            CFStringRef uid = nullptr; UInt32 uid_size = sizeof(uid);
            checked(AudioObjectGetPropertyData(devices[i], &uid_address, 0, nullptr, &uid_size, &uid), "device UID");
            if (!uid) throw std::runtime_error("empty CoreAudio UID");
            // The caller owns the returned CF object, including on conversion errors.
            auto release = [](const void* value) { CFRelease(value); };
            std::unique_ptr<const void, decltype(release)> owned(uid, release);
            auto capacity = CFStringGetMaximumSizeForEncoding(CFStringGetLength(uid), kCFStringEncodingUTF8) + 1;
            std::vector<char> bytes(static_cast<std::size_t>(capacity));
            if (!CFStringGetCString(uid, bytes.data(), capacity, kCFStringEncodingUTF8))
                throw std::runtime_error("CoreAudio UID conversion failed");
            result.identities.push_back({identity_hash("coreaudio-uid-v1", bytes.data()), DeviceIdentity::Scope::CoreAudioUID});
        }
        break;
    }
    auto has_default = [&](unsigned index) {
        AudioDeviceID device = kAudioObjectUnknown; UInt32 size = sizeof(device);
        checked(AudioObjectGetPropertyData(kAudioObjectSystemObject, &addresses[index], 0, nullptr, &size, &device), "default device");
        return device != kAudioObjectUnknown;
    };
    result.default_input_present = has_default(1);
    result.default_output_present = has_default(2);
#endif
    return result;
}
}
