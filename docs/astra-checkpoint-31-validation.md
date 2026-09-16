# Astra checkpoint 31 validation

470 Python tests passed on 2026-09-13. Three new tests use actual private credential
files with deterministic event-wait substitution to verify revoked batch rejection,
malformed-file idle closure, normal event/heartbeat delivery and slot release.
The stream wrapper is real; the event producer and response header methods are
stubbed. Existing HTTP stream-capacity and credential-rotation coverage also passes.

File-backed SSE authority is rechecked around waits and before event writes. Idle
waits are one second; this is not a guaranteed end-to-end revocation latency.
Already-sent bytes, blocked writes, scheduling and in-flight backend mutations are
outside immediate revocation. Environment-only sessions remain snapshot-based.

No native changes or fresh native/sanitizer build. CMake/CTest prerequisites remain
unavailable. No live credentials, service deployment or physical hardware changed.
Next: per-user control roles and durable actor/action authorization auditing.
