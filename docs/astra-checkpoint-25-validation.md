# Astra checkpoint 25 validation

436 Python tests passed on 2026-09-13. Two new real-socket tests continuously
trickle header/body bytes every 25 ms against a 200 ms test receive budget and
one-second inactivity timeout; both connections close before route mutation.
Existing bounded-server stream/control and capacity tests also pass.

Production receive budget is 15 seconds per request, including keep-alive waiting,
headers and JSON body. Responses restore the ten-second inactivity timeout.
This is not a backend execution deadline, rate limiter or complete LAN review.
No native source changes or fresh native build; CMake/CTest sanitizer prerequisites
remain unavailable. Remaining: request rate limits, proxy/TLS, authorization,
secret lifecycle and audit retention.
