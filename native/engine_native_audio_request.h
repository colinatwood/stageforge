#pragma once

#include "audio_preflight.h"

#include <cstdint>
#include <string_view>

namespace stageforge {

// Translate the recovered engine's AUDIO_* activation contract into the native
// endpoint request used by WASAPI/CoreAudio. This is intentionally stricter than
// ALSA: the native stream is float32-only and does not claim conversions that it
// does not itself implement.
bool make_engine_native_audio_request(AudioDirection direction,
                                      double sample_rate,
                                      std::uint32_t period_frames,
                                      std::uint32_t channels,
                                      std::string_view sample_format,
                                      std::uint32_t conversion_flags,
                                      AudioRequest& request) noexcept;

} // namespace stageforge
