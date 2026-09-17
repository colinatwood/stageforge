from pathlib import Path

path = Path('native/src/engine_main.cpp')
text = path.read_text(encoding='utf-8')


def replace_between(start, end, replacement):
    global text
    i = text.index(start)
    j = text.index(end, i)
    text = text[:i] + replacement + text[j:]

include_anchor = '#include "engine_native_audio_command.h"\n'
if '#include "engine_native_audio_status.h"' not in text:
    text = text.replace(include_anchor, include_anchor + '#include "engine_native_audio_status.h"\n', 1)

input_block = '''        if (command == "AUDIO_INPUT_STATUS" && (parts.size() == 1 || parts.size() == 2)) {
            std::size_t slot = 0;
            if (parts.size() == 2 && (!parse_number(parts[1], slot) || slot >= kAudioInputSlots)) { error("argument", "invalid audio input slot"); continue; }
            const auto stream = alsa_inputs[slot].status();
            const auto requested = alsa_inputs[slot].requested_config();
            const bool alsa = execution_audio_input_backends[slot] == "alsa";
#if defined(_WIN32) || defined(__APPLE__)
            const auto native = stageforge::project_engine_native_audio_status(native_audio.capture_stats(slot));
            const bool native_execution = execution_audio_input_backends[slot] == "wasapi" || execution_audio_input_backends[slot] == "coreaudio";
#else
            const stageforge::EngineNativeAudioStatus native{};
            const bool native_execution = false;
#endif
            const auto queued = ([&](){ std::uint64_t total=0; for(std::size_t reader=0; reader<kAudioOutputSlots; ++reader) total += audio_inputs[slot].ring.queued(reader); return total; })();
            const auto dropped = ([&](){ std::uint64_t total=0; for(std::size_t reader=0; reader<kAudioOutputSlots; ++reader) total += audio_inputs[slot].ring.dropped(reader); return total; })();
            const auto underruns = ([&](){ std::uint64_t total=0; for(std::size_t reader=0; reader<kAudioOutputSlots; ++reader) total += audio_inputs[slot].ring.underruns(reader); return total; })();
            std::cout << "OK slot=" << slot
                      << " execution=" << execution_audio_input_backends[slot]
                      << " selected=" << (selected_audio_inputs[slot].empty() ? "none" : selected_audio_inputs[slot])
                      << " state=" << static_cast<int>(native_execution ? (native.running ? stageforge::AudioDeviceState::running : stageforge::AudioDeviceState::closed) : stream.state)
                      << " callbacks=" << (native_execution ? native.callbacks : stream.callback_count)
                      << " xruns=" << (alsa ? stream.xruns : 0)
                      << " discontinuities=" << (native_execution ? native.discontinuities : 0)
                      << " sampleRate=" << audio_inputs[slot].sample_rate.load(std::memory_order_acquire)
                      << " requestedRate=" << (native_execution ? native.sample_rate_hz : requested.sample_rate)
                      << " configuredRate=" << (native_execution ? native.sample_rate_hz : stream.config.sample_rate)
                      << " periodFrames=" << (native_execution ? native.period_frames : stream.config.frames_per_buffer)
                      << " channels=" << (native_execution ? native.channels : stream.config.input_channels)
                      << " requestedPeriodFrames=" << (native_execution ? native.period_frames : requested.frames_per_buffer)
                      << " requestedChannels=" << (native_execution ? native.channels : requested.input_channels)
                      << " sampleFormat=" << (native_execution ? native.sample_format : token_safe(alsa_inputs[slot].sample_format()))
                      << " source=" << static_cast<unsigned int>(audio_inputs[slot].source.load(std::memory_order_acquire))
                      << " queued=" << queued << " dropped=" << dropped << " underruns=" << underruns
                      << " error=" << (native_execution ? (native.callback_fault ? "callback_fault" : "none") : token_safe(alsa_inputs[slot].last_error().empty() ? "none" : alsa_inputs[slot].last_error()))
                      << '\\n' << std::flush;
            continue;
        }
'''
replace_between('        if (command == "AUDIO_INPUT_STATUS"', '        if (command == "AUDIO_INPUT_ROUTE"', input_block)

stream_block = '''        if (command == "AUDIO_STREAM_STATUS" && (parts.size() == 1 || parts.size() == 2)) {
            std::size_t slot = 0;
            if (parts.size() == 2 && (!parse_number(parts[1], slot) || slot >= kAudioOutputSlots)) { error("argument", "invalid audio output slot"); continue; }
            const auto stream = alsa_outputs[slot].status();
            const auto requested = alsa_outputs[slot].requested_config();
            const bool alsa = execution_audio_backends[slot] == "alsa";
#if defined(_WIN32) || defined(__APPLE__)
            const auto native = stageforge::project_engine_native_audio_status(native_audio.playback_stats(slot));
            const bool native_execution = execution_audio_backends[slot] == "wasapi" || execution_audio_backends[slot] == "coreaudio";
#else
            const stageforge::EngineNativeAudioStatus native{};
            const bool native_execution = false;
#endif
            std::uint64_t fanout_dropped = 0, fanout_underruns = 0, fanout_queued = 0;
            for (const auto& input : audio_inputs) { fanout_dropped += input.ring.dropped(slot); fanout_underruns += input.ring.underruns(slot); fanout_queued += input.ring.queued(slot); }
            const auto start_ns = audio_render_contexts[slot].drift_start_ns.load(std::memory_order_relaxed);
            const auto last_ns = audio_render_contexts[slot].drift_last_ns.load(std::memory_order_relaxed);
            const bool streaming = alsa || native_execution;
            const bool rate_measured = streaming && start_ns > 0 && last_ns > start_ns && (last_ns - start_ns) >= 50'000'000ULL;
            const auto null_status = audio.status();
            const auto state = native_execution ? (native.running ? stageforge::AudioDeviceState::running : stageforge::AudioDeviceState::closed) : (alsa ? stream.state : (slot == 0 ? null_status.state : stageforge::AudioDeviceState::closed));
            std::cout << "OK slot=" << slot << " execution=" << execution_audio_backends[slot]
                      << " selected=" << (selected_audio_outputs[slot].empty() ? "none" : selected_audio_outputs[slot])
                      << " state=" << static_cast<int>(state)
                      << " callbacks=" << (native_execution ? native.callbacks : (alsa ? stream.callback_count : (slot == 0 ? null_status.callback_count : 0)))
                      << " xruns=" << (alsa ? stream.xruns : 0)
                      << " discontinuities=" << (native_execution ? native.discontinuities : 0)
                      << " requestedRate=" << (native_execution ? native.sample_rate_hz : (alsa ? requested.sample_rate : (slot == 0 ? null_status.config.sample_rate : 0.0)))
                      << " configuredRate=" << (native_execution ? native.sample_rate_hz : (alsa ? stream.config.sample_rate : (slot == 0 ? null_status.config.sample_rate : 0.0)))
                      << " periodFrames=" << (native_execution ? native.period_frames : (alsa ? stream.config.frames_per_buffer : (slot == 0 ? null_status.config.frames_per_buffer : 0)))
                      << " channels=" << (native_execution ? native.channels : (alsa ? stream.config.output_channels : (slot == 0 ? null_status.config.output_channels : 0)))
                      << " requestedPeriodFrames=" << (native_execution ? native.period_frames : (alsa ? requested.frames_per_buffer : (slot == 0 ? null_status.config.frames_per_buffer : 0)))
                      << " requestedChannels=" << (native_execution ? native.channels : (alsa ? requested.output_channels : (slot == 0 ? null_status.config.output_channels : 0)))
                      << " sampleFormat=" << (native_execution ? native.sample_format : (alsa ? token_safe(alsa_outputs[slot].sample_format()) : "FLOAT_LE"))
                      << " output=" << static_cast<unsigned int>(audio_render_contexts[slot].output.load(std::memory_order_acquire))
                      << " queued=" << fanout_queued << " dropped=" << fanout_dropped << " underruns=" << fanout_underruns
                      << " rateMeasured=" << (rate_measured ? 1 : 0)
                      << " ratePpm=" << std::fixed << std::setprecision(2) << audio_render_contexts[slot].measured_rate_ppm.load(std::memory_order_relaxed)
                      << " driftEnabled=" << (audio_render_contexts[slot].drift_enabled.load(std::memory_order_relaxed) ? 1 : 0)
                      << " maxCorrectionPpm=" << audio_render_contexts[slot].max_correction_ppm.load(std::memory_order_relaxed)
                      << " queueGainPpm=" << audio_render_contexts[slot].queue_gain_ppm.load(std::memory_order_relaxed)
                      << " correctionPpm=" << audio_render_contexts[slot].correction_ppm.load(std::memory_order_relaxed)
                      << " sourceFrames=" << audio_render_contexts[slot].source_frames_last.load(std::memory_order_relaxed)
                      << " compensatedBlocks=" << audio_render_contexts[slot].compensated_blocks.load(std::memory_order_relaxed)
                      << " firstWriteNs=" << (alsa ? alsa_outputs[slot].first_write_ns() : 0)
                      << " lastWriteNs=" << (alsa ? alsa_outputs[slot].last_write_ns() : 0)
                      << " maxExcessGapNs=" << (alsa ? alsa_outputs[slot].max_excess_gap_ns() : 0)
                      << " framesWritten=" << (native_execution ? native.frames : (alsa ? alsa_outputs[slot].frames_written() : 0))
                      << " firstRenderShowNs=" << audio_render_contexts[slot].first_render_show_ns.load(std::memory_order_relaxed)
                      << " lastRenderShowNs=" << audio_render_contexts[slot].last_render_show_ns.load(std::memory_order_relaxed)
                      << " lastBlockEndShowNs=" << audio_render_contexts[slot].last_block_end_show_ns.load(std::memory_order_relaxed)
                      << " error=" << (native_execution ? (native.callback_fault ? "callback_fault" : "none") : token_safe(alsa_outputs[slot].last_error().empty() ? "none" : alsa_outputs[slot].last_error()))
                      << '\\n' << std::flush;
            continue;
        }
'''
replace_between('        if (command == "AUDIO_STREAM_STATUS"', '        if (command == "AUDIO_ROUTE"', stream_block)

status_start = '        } else if (command == "STATUS") {'
status_end = '        } else if (command == "QUIT") {'
i = text.index(status_start)
j = text.index(status_end, i)
old = text[i:j]
old = old.replace('std::uint64_t output_callbacks = 0, output_xruns = 0;', 'std::uint64_t output_callbacks = 0, output_xruns = 0, output_discontinuities = 0;')
old = old.replace('output_callbacks += output_status.callback_count; output_xruns += output_status.xruns;\n                if (execution_audio_backends[slot] == "alsa" || (slot == 0 && execution_audio_backends[slot] == "null-audio")) ++active_outputs;', '''if (execution_audio_backends[slot] == "alsa") { output_callbacks += output_status.callback_count; output_xruns += output_status.xruns; ++active_outputs; }
#if defined(_WIN32) || defined(__APPLE__)
                else if (execution_audio_backends[slot] == "wasapi" || execution_audio_backends[slot] == "coreaudio") { const auto native = stageforge::project_engine_native_audio_status(native_audio.playback_stats(slot)); output_callbacks += native.callbacks; output_discontinuities += native.discontinuities; if (native.running) ++active_outputs; }
#endif
                else if (slot == 0 && execution_audio_backends[slot] == "null-audio") { output_callbacks += audio_status.callback_count; ++active_outputs; }''')
old = old.replace('std::uint64_t input_callbacks = 0, input_xruns = 0, input_queued = 0;', 'std::uint64_t input_callbacks = 0, input_xruns = 0, input_discontinuities = 0, input_queued = 0;')
old = old.replace('input_callbacks += input_status.callback_count; input_xruns += input_status.xruns;', '''if (execution_audio_input_backends[slot] == "alsa") { input_callbacks += input_status.callback_count; input_xruns += input_status.xruns; }
#if defined(_WIN32) || defined(__APPLE__)
                else if (execution_audio_input_backends[slot] == "wasapi" || execution_audio_input_backends[slot] == "coreaudio") { const auto native = stageforge::project_engine_native_audio_status(native_audio.capture_stats(slot)); input_callbacks += native.callbacks; input_discontinuities += native.discontinuities; }
#endif''')
old = old.replace('<< " audioXruns=" << output_xruns', '<< " audioXruns=" << output_xruns\n                      << " audioDiscontinuities=" << output_discontinuities')
old = old.replace('<< " audioInputXruns=" << input_xruns', '<< " audioInputXruns=" << input_xruns\n                      << " audioInputDiscontinuities=" << input_discontinuities')
text = text[:i] + old + text[j:]

path.write_text(text, encoding='utf-8')
