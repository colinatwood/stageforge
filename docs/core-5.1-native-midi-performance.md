# Core 5.1 native MIDI performance

Core 5.1 moves the first production-critical subset of MIDI mapping execution from the development bridge into native Core. Persisted mappings for transport play/stop, master tempo, filter cutoff/resonance, track volume and track pan are compiled into the fixed-capacity native router.

## Execution path

1. The platform MIDI adapter produces a bounded `CapturedMidiInput` record with device identity and Show Time.
2. `MidiLearnRouter` matches device, channel, message and control number; applies absolute, relative, trigger, toggle or gate behavior; and computes the musical boundary.
3. `MidiMappedActionDispatcher` converts the result into an authoritative transport or automation `ShowEvent` with a unique replay-safe event ID.
4. The existing `ShowExecutionLoop` accepts the event and remains the sole owner of timeline ordering and dispatch.
5. The native transport or automation state applies the due event and CoreJournal records the execution.

The Python service still persists mapping documents, feeds musician-facing observation, and compiles eligible mappings into Core. It records which mapping IDs Core accepted and will not execute those actions again. This is a migration boundary, not two authorities.

## Deliberate limits

- Sample trigger, loop toggle/clear and key-synchronized instrument targets remain on the bridge execution path. Core 5.1 does not disguise the arrangement playback queue as a polyphonic sampler.
- Mapping compilation does not arm audio, audio input, lighting or any other physical output.
- Compiled mappings are volatile native execution state. Restart begins empty and the persistent service recompiles them only after the normal authority-controlled startup path.
- Standby nodes remain unable to attach authoritative MIDI input under the existing node authority policy.

## Development protocol

- `MIDI_MAP_MASTER <bpm> <key-root> <scale-mask>`
- `MIDI_MAP_UPSERT <mapping-id> <device-id> <target-id> <parameter-id> <channel> <number> <message> <behavior> <action> <steps-per-beat> <key-sync> <minimum> <maximum>`
- `MIDI_MAP_REMOVE <mapping-id>`
- `MIDI_MAP_CLEAR`
- `MIDI_MAP_STATUS`

The public provider-neutral contract is `org.upp.midi.native-performance/1`. The stdio commands are a local development surface and are not the interoperability standard.
