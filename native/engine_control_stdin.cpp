#include "engine_control_stdin.h"

#if defined(_WIN32)
#include <windows.h>
#else
#include <cerrno>
#include <poll.h>
#endif

namespace stageforge {

EngineControlWaitResult wait_engine_stdin(std::uint32_t timeout_ms) noexcept {
#if defined(_WIN32)
    const HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    if (input == nullptr || input == INVALID_HANDLE_VALUE) return EngineControlWaitResult::failed;
    const DWORD result = WaitForSingleObject(input, static_cast<DWORD>(timeout_ms));
    if (result == WAIT_TIMEOUT) return EngineControlWaitResult::timeout;
    if (result == WAIT_OBJECT_0) return EngineControlWaitResult::ready;
    return EngineControlWaitResult::failed;
#else
    pollfd descriptor{};
    descriptor.fd = 0;
    descriptor.events = POLLIN | POLLHUP;
    int result = 0;
    do {
        result = ::poll(&descriptor, 1, static_cast<int>(timeout_ms));
    } while (result < 0 && errno == EINTR);
    if (result == 0) return EngineControlWaitResult::timeout;
    if (result < 0 || (descriptor.revents & (POLLERR | POLLNVAL)) != 0) return EngineControlWaitResult::failed;
    if ((descriptor.revents & POLLIN) != 0) return EngineControlWaitResult::ready;
    if ((descriptor.revents & POLLHUP) != 0) return EngineControlWaitResult::closed;
    return EngineControlWaitResult::failed;
#endif
}

} // namespace stageforge
