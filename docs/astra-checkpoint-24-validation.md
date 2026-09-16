# Astra checkpoint 24 validation

2026-09-13: separate event-stream admission.

434 Python tests passed. Three new tests cover normal and exceptional stream-slot
release plus a real HTTP integration with one occupied stream slot, a rejected
second stream and successful ordinary control response. That test substitutes a
controlled stream producer; existing API coverage exercises the actual event route.

CLI policy: eight concurrent SSE streams inside 32 worker connections. Excess
streams receive 503 and Retry-After: 5. Ended streams close their HTTP connection.
This does not reserve priority for control traffic against ordinary connection
floods. Total request deadlines, rate limits, proxy/TLS and authorization remain
open. No native sources changed; no fresh native/sanitizer build is claimed.
The suite still reports unavailable CMake/CTest sanitizer prerequisites.
