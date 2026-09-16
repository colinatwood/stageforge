# Astra checkpoint 22 validation

2026-09-13: HTTP framing and rejected-body isolation.

427 Python tests passed, including six new raw-socket tests covering malformed
framing, rejected-body pipeline isolation, Expect rejection, GET-body rejection,
truncated JSON and valid keep-alive requests. No native sources changed.
The suite reports unavailable CMake/CTest sanitizer prerequisites; no fresh native
build or sanitizer qualification is claimed for this checkpoint.

Remaining priorities: proxy/TLS trust, secret lifecycle, role authorization,
connection/rate limits, slow-client deadlines, SSE budgets, audit retention and
witness trust/clock assumptions. Browser and physical hardware qualification remain
deferred/unverified as previously documented. Do not treat this as LAN approval.
