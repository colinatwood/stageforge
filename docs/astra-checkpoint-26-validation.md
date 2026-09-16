# Astra checkpoint 26 validation

440 Python tests passed on 2026-09-13. Four new tests exercise per-peer refill,
aggregate rejection, bounded identity admission and real HTTP throttling despite
a changed forwarded address. The HTTP rate test uses a fixed clock to avoid
scheduler-dependent refill. No native sources changed; no fresh native build or
sanitizer qualification is claimed. CMake/CTest prerequisites remain unavailable.

Limits apply to the CLI bounded server, including loopback and static requests.
Proxied clients share one direct-peer bucket. Workload qualification, backend cost
bounds, proxy/TLS trust, authorization, secret lifecycle and audit retention remain
open; this checkpoint does not grant LAN release readiness.
