# StageForge

This repository consolidates the recovered Checkpoint 69 engine, backend,
frontend, schemas, packaging and tests with the Checkpoint 70–83 platform work.
GitHub is the canonical source. Recovery provenance and integration limits are
recorded in `docs/consolidation-checkpoint-84.md`.

Build the engine from the repository root with `cmake -S . -B build`, then
`cmake --build build --config Release` and
`ctest --test-dir build -C Release --output-on-failure`.
On Windows and macOS this also builds the native device lifecycle components.
Their standalone build remains available with `cmake -S native -B build`.

The Linux developer-alpha software gate is `python scripts/release-check.py`.
Install its build requirements from `requirements-release.txt` and provide Node.js.
Hosted software evidence does not qualify physical audio/MIDI hardware, licensed
plugins, deployed services, or installed packages. See
`docs/remaining-data-requirements.md` for remaining acceptance inputs.
