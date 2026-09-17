cmake_minimum_required(VERSION 3.20)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(STAGEFORGE_DEVICE_ASAN "Enable AddressSanitizer for device lifecycle tests" OFF)

add_library(stageforge_devices
  device_monitor.cpp
  device_identity.cpp
  device_execution_fence.cpp
  audio_preflight.cpp
  audio_stream_lifecycle.cpp
  software_audio_render.cpp
  native_endpoint_stream.cpp
  engine_native_audio_bridge.cpp
  engine_native_audio_request.cpp
  engine_native_audio_callbacks.cpp
  engine_native_audio_runtime.cpp
  engine_native_audio_command.cpp
  engine_control_loop.cpp
  engine_control_stdin.cpp)
target_include_directories(stageforge_devices PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

if(WIN32)
  include(CheckCXXSourceCompiles)
  check_cxx_source_compiles(
    "#include <windows.h>\n#include <mmdeviceapi.h>\nint main(){ (void)PKEY_AudioEndpoint_StableId; return 0; }"
    STAGEFORGE_HAS_AUDIOENDPOINT_STABLEID)
  if(STAGEFORGE_HAS_AUDIOENDPOINT_STABLEID)
    target_compile_definitions(stageforge_devices PRIVATE STAGEFORGE_HAS_AUDIOENDPOINT_STABLEID=1)
  else()
    target_compile_definitions(stageforge_devices PRIVATE STAGEFORGE_HAS_AUDIOENDPOINT_STABLEID=0)
  endif()
  target_link_libraries(stageforge_devices PUBLIC ole32 uuid winmm cfgmgr32)
elseif(APPLE)
  target_link_libraries(stageforge_devices PUBLIC "-framework CoreAudio" "-framework CoreMIDI" "-framework CoreFoundation" "-framework AudioToolbox" "-framework AudioUnit")
  if(STAGEFORGE_DEVICE_ASAN)
    target_compile_options(stageforge_devices PRIVATE -fsanitize=address -fno-omit-frame-pointer)
  endif()
else()
  message(FATAL_ERROR "Device monitor requires Windows or macOS")
endif()

set(STAGEFORGE_DEVICE_SMOKES
  device_lifecycle
  device_execution_fence
  audio_preflight
  audio_stream_lifecycle
  native_playback
  native_capture
  native_selected_loss
  engine_native_audio_bridge
  engine_native_audio_request
  engine_native_audio_callbacks
  engine_native_audio_runtime
  engine_native_audio_command
  engine_control_loop
  engine_control_stdin
  engine_native_audio_runtime_state)
foreach(smoke IN LISTS STAGEFORGE_DEVICE_SMOKES)
  add_executable(${smoke}_smoke ${smoke}_smoke.cpp)
  target_link_libraries(${smoke}_smoke PRIVATE stageforge_devices)
  if(APPLE AND STAGEFORGE_DEVICE_ASAN)
    target_compile_options(${smoke}_smoke PRIVATE -fsanitize=address -fno-omit-frame-pointer)
    target_link_options(${smoke}_smoke PRIVATE -fsanitize=address)
  endif()
endforeach()

enable_testing()
foreach(smoke IN LISTS STAGEFORGE_DEVICE_SMOKES)
  add_test(NAME ${smoke} COMMAND ${smoke}_smoke)
  set_tests_properties(${smoke} PROPERTIES TIMEOUT 30)
endforeach()
