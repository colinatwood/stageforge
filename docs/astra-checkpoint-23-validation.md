# Astra checkpoint 23 validation

2026-09-13: bounded HTTP workers and inactive socket protection.

431 Python tests passed, including four new capacity/failure/idle-header tests.
The CLI now uses the bounded server; prior tests constructing a generic
ThreadingHTTPServer still exercise route behavior rather than admission policy.
No native sources changed and no fresh native build is claimed. CMake/CTest
sanitizer prerequisites remain unavailable in this environment.

Limits: 32 worker connections and ten seconds of socket I/O inactivity. Rejected
excess connections close without an HTTP response. SSE shares the worker pool.
These limits bound worker growth but do not guarantee control availability under
attack. Total request deadlines, reserved control capacity, separate SSE admission,
rate limiting, proxy/TLS review and authorization review remain outstanding.
