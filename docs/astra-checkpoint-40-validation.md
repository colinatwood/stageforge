# Astra backlog checkpoint 40 validation

Checkpoint 40 closes the software-side **DAW temporary-resource crash/power-loss recovery** gap. It does not claim physical storage power-loss qualification, recording-publication directory durability, or real-plugin qualification.

## Delivered

- Added one internal version-2 temporary-resource owner manifest shared by render/import staging, media snapshots and isolated plugin scratch.
- Owner evidence now binds exact process generation (`bootId` + `processStartTicks`) to the exact filesystem object (`device`, `inode`, `kind`) plus bounded resource class/purpose metadata.
- Owner manifests are atomically replaced from a private temporary file, fsynced before publication, and followed by a parent-directory fsync. Directory-backed resources additionally sync their containing store after the resource directory and manifest exist.
- Missing, malformed, legacy, symlinked, replaced or otherwise unverifiable resources are `unknown-owner` and are never automatically reclaimed.
- Proven-dead cleanup reloads the manifest and rechecks the exact resource identity immediately before deletion. A stale manifest cannot authorize deletion after pathname replacement.
- Manifest/directory durability failures clean newly-created staged resources instead of leaving an apparently owned artifact behind.
- An unclean subprocess exit regression proves a durable staged resource becomes reclaimable only after the exact recorded process generation is gone.
- No physical input/output authority, show-time behavior, native ABI or public JSON schema changed.

## Focused evidence

The temporary-resource focused suite contains **38 passing tests** covering:

- fsynced atomic manifest publication;
- exact dead-owner reclamation;
- missing/malformed/legacy preservation;
- inode replacement preservation;
- unclean subprocess exit and subsequent reclaim;
- staged-file manifest failure cleanup;
- media-snapshot dead/live/unknown classification and replacement preservation;
- media-snapshot store-sync failure cleanup/reservation release;
- plugin-scratch dead/unknown cleanup and pre-launch durability failure cleanup;
- aggregate DAW temporary-resource API safety.

## Release gate

- Fresh RT-qualification native build: **passed**.
- Native CTest: **2/2 passed**.
- Release Python suite: **524 tests passed**, zero skips.
- Automation performance: **passed** (`4096` points, `8192` frames, binary block-entry search).
- JSON schema set: **117 parsed**.
- OpenAPI 3.1 document: **parsed**.
- Frontend JavaScript: **7/7** syntax checks passed.

## Still open

- Recording publication still needs parent-directory durability after the hard-link publication and partial-file cleanup boundary (checkpoint 41 / `DAW-034`).
- Physical filesystem/power-cut qualification remains hardware/environment evidence, not established by software fault injection.
- Real-plugin and named-hardware soak remain separate qualification work.
