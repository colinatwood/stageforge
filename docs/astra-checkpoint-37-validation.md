# Astra checkpoint 37 validation

Updated 2026-09-13. This checkpoint bounds concurrent expensive HTTP work without changing real-time/native execution or force-cancelling stateful operations.

## Admission contract

The development bridge retains its 32-worker connection cap. Known expensive requests additionally share a four-request total budget with class caps:

- maintenance: 1
- discovery: 2
- planning: 3
- storage: 2
- external delivery: 2

Admission is non-blocking. A saturated expensive request returns `503` plus `Retry-After: 1` before its body is read. Ordinary health/control routes remain outside the expensive budget. Each acquired slot is returned in the request handler `finally` path, including after an injected route crash.

The current registry covers checkpoint/audit/public-record maintenance, audio/MIDI/hardware discovery, compatibility/venue/technology/interoperability planning, DAW media ingest/verify/render/autosave and temporary-resource cleanup, plus community vote-email delivery.

## Regression evidence

`python3 -m unittest -v tests.test_http_operation_cost`

Result: 4 tests passed. They verify exact route classification, per-class isolation, rejection before body execution while a cheap request still succeeds, and capacity reclamation after route failure.

## Release validation

The release Python suite ran against the fresh RT-qualified native engine with system Python first on `PATH`: **510 tests passed with zero skips**. Additional gates passed:

- Native CTest: **2/2**.
- `scripts/automation-performance.py --json`: passed.
- OpenAPI parsed successfully.
- All **117** JSON schemas parsed successfully.
- All **7** frontend JavaScript files passed `node --check`.

## Remaining boundary

These are software admission bounds, not a performance certification. Real controller workload/rate-policy qualification, deployed proxy/IdP/firewall behavior, independent witness/clock assumptions and hardware timing still remain open.
