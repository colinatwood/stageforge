# Core 5.2 disciplined transport and MIDI Clock

Core 5.2 begins by making clock evidence operational rather than merely observable. A source adapter supplies paired local/source monotonic timestamps and its source Show Time. Core estimates source rate, measures phase error against local Show Time and publishes a bounded transport-rate command. It never corrects phase by seeking.

## Authority and continuity

Configuration binds one source identity to the active authority epoch, a holdover threshold, maximum slew in parts per million and a phase-recovery window. Observations must carry that epoch and a strictly advancing sequence. Wrong-epoch, replayed and malformed evidence is rejected before it can affect transport.

While locked, the applied correction combines estimated drift with phase error divided across the recovery window, clamped to the configured slew ceiling. A 1 ms phase error with a 5 second window therefore requests roughly 200 ppm before drift is included. When evidence ages past the holdover threshold, phase recovery is removed and Core continues at the learned rate. Show position remains monotonic throughout loss and recovery.

## MIDI Clock

The native MIDI Clock engine represents 24 pulses per quarter note directly in Show Time. Configure, start, stop, tempo change and input observation are authority-epoch fenced. Output planning uses a fractional nanosecond accumulator so rounding does not compound across pulses. Tempo changes establish a declared exact boundary; they do not reset transport or reinterpret earlier pulses.

Generated MIDI Start (`0xFA`), Clock (`0xF8`) and Stop (`0xFC`) messages enter the existing bounded MIDI scheduler. A platform MIDI adapter still owns actual device transmission and explicit output authority. Input pulses require advancing sequence identity and publish learned BPM plus maximum observed interval jitter.

## Development protocol

- `TRANSPORT_DISCIPLINE_CONFIG <source-id> <epoch> <holdover-ns> <max-slew-ppm> <recovery-window-ns>`
- `TRANSPORT_DISCIPLINE_OBSERVE <sequence> <epoch> <local-ns> <source-ns> <local-show-ns> <source-show-ns>`
- `TRANSPORT_DISCIPLINE_STATUS [local-ns]`
- `MIDI_CLOCK_CONFIG <epoch> <bpm> <boundary-show-ns>`
- `MIDI_CLOCK_START <epoch> <boundary-show-ns>`
- `MIDI_CLOCK_STOP <epoch> <show-ns>`
- `MIDI_CLOCK_TEMPO <epoch> <bpm> <boundary-show-ns>`
- `MIDI_CLOCK_OBSERVE <epoch> <sequence> <show-ns>`
- `MIDI_CLOCK_EMIT <until-show-ns> [maximum]`
- `MIDI_CLOCK_STATUS`

The provider-neutral extensions are `org.upp.timing.transport-discipline/1` and `org.upp.midi.clock-24ppqn/1`. Software timing tests are not hardware jitter qualification, and no clock operation arms physical output.
