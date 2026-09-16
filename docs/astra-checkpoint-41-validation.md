# Astra backlog checkpoint 41 validation

Checkpoint 41 closes the software-side **recording publication parent-directory durability** gap on the current Linux path. It does not claim physical storage/power-cut qualification.

## Delivered

- Added shared same-directory durability primitives for non-replacing hard-link publication and unlink-directory synchronization.
- Recording finalization now orders durability as: close WAV header, fsync completed file bytes, create the non-replacing target hard link, fsync the parent directory, remove the partial path, then fsync the parent directory again.
- Failure of the first parent-directory sync never reports success. The just-created target is removed best-effort and the sealed partial remains attached so finalization can be retried.
- Once target publication is durably committed, later partial-file unlink or cleanup-directory-sync failure reports `partialCleanupPending: true` without demoting the already durable recording.
- Successful capture receipts now report `directoryDurable: true`.
- Interrupted-recording recovery uses the same durable hard-link publication boundary for recovered WAVs and reports `directoryDurable: true`; temporary recovery cleanup remains separately observable.
- Existing non-overwrite semantics, physical-input disarm, dropout evidence and retry behavior remain intact.

## Focused evidence

The recording-focused suite contains **20 passing tests** covering normal finish/recovery, collision handling, file-fsync failure, publication failure, parent-directory-sync rollback, cleanup-directory-sync degradation, stalled capture, punch completion, partial recovery, malformed input and browser recovery workflow.

## Release gate

- Fresh RT-qualification native build: **passed**.
- Native CTest: **2/2 passed**.
- Release Python suite: **527 tests passed**, zero skips.
- Automation performance: **passed** (`4096` points, `8192` frames, binary block-entry search).
- JSON schema set: **117 parsed**.
- OpenAPI 3.1 document: **parsed**.
- Frontend JavaScript: **7/7** syntax checks passed.

## Still open

- Physical storage/power-cut testing remains external qualification evidence.
- Audible recording correctness on named interfaces remains deferred hardware work.
- Arrangement playback still has a restricted loop-length implementation; arbitrary sample-exact loop wrapping is the next local DAW software seam.
