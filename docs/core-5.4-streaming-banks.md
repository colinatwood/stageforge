# Core 5.4 replaceable streaming sample banks

Core 5.4 groups long DAW audio clips into 16 replaceable banks of up to 64 entries. Unlike the allocation-free voice sampler, bank entries are not copied into fixed native asset memory and therefore are not limited to 65,536 frames. A service-thread producer reads and converts media into bounded 256-frame blocks ahead of the generation-fenced native playback queue.

Replacing a bank atomically advances its generation. Entries retain stable DAW clip IDs, labels, modes and SHA-256 content identities. Both registration and triggering verify the source bytes; missing or changed content refuses execution until the bank is explicitly relinked or replaced. Trigger action IDs use a bounded 256-entry replay window.

Disk access, hashing, decoding, allocation and locks remain outside the real-time callback. Queue underrun/discontinuity behavior remains observable through the existing playback status. Bank actions do not arm physical outputs.

Checkpoint 18 adds the native polyphonic target: 16 fixed streaming voice slots, each with its own eight-block SPSC feed, generation and sequence fence, cursor, gain, terminal/loop state and starvation evidence. Output zero mixes these voices as source 23. Native start/block/stop/status commands accept at most 256 stereo frames per feed block and report an active mask for lifecycle reclamation. The callback performs only bounded queue consumption and mixing; it never opens or decodes media.

Bank triggers now allocate an independent slot, decode up to four blocks on the control thread before queueing start, and continue long or looping clips on a dedicated service thread. Native feed pressure is retried only for a bounded 250 ms per block. Each stop names both slot and generation; shutdown cancels and joins every feeder before issuing stop-all. Slots are reclaimed only when the callback reports the exact generation inactive, avoiding time-based reuse guesses.

The extension is `org.upp.audio.streaming-sample-bank/1` in public C ABI 1.61.
