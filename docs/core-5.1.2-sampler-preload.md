# Core 5.1.2 verified DAW sampler preload

Core 5.1.2 connects short DAW audio clips to the Core 5.1.1 voice engine without weakening its real-time contract. All path resolution, hashing, WAV decoding, rate conversion and gain/fade preparation occurs on a control thread before immutable PCM is published to native Core.

## Promotion fence

A sample or loop mapping is native-eligible only when its clip:

1. still exists in the current normalized DAW session;
2. references an `audio-file` source within the managed media root;
3. matches its declared SHA-256 content identity when one is present;
4. contains no more than 65,536 canonical frames; and
5. has been accepted by the native sampler.

The published identity includes session revision, source hash, source offset, clip length, one-shot/loop mode and choke group. Any change produces a distinct native resource ID. Mapping compilation substitutes that generation-specific ID, so a newly compiled gesture cannot select stale PCM.

One-shot and loop versions are separate immutable assets because their playback semantics differ. Loop assets use a bounded equal-power crossfade. Track gain, equal-power pan and clip fades are baked during preload; velocity remains a real-time voice parameter.

## Recovery and limits

Eligible persisted mappings are restored during normal native startup. Learn mode preloads the selected clip before waiting for the controller gesture, keeping file I/O out of the MIDI capture loop. Explicit preload is also available through `POST /api/v1/daw/sampler/preload`; status and native telemetry are available through `GET /api/v1/daw/sampler`.

The native process retains immutable generations until restart and accepts at most 32 published generations. Longer clips, streaming libraries, eviction and live bank replacement remain future provider work. Refused assets keep their mappings on the existing arrangement-producer path, and no preload or mapping operation arms physical output.
