#include "engine_control_stdin.h"

int main() {
    const auto result = stageforge::wait_engine_stdin(0);
    switch (result) {
        case stageforge::EngineControlWaitResult::ready:
        case stageforge::EngineControlWaitResult::timeout:
        case stageforge::EngineControlWaitResult::closed:
        case stageforge::EngineControlWaitResult::failed:
            return 0;
    }
    return 1;
}
