# Astra checkpoint 27 validation

450 Python tests passed on 2026-09-13, ten more than checkpoint 26.

Covered findings: localhost privilege inheritance in proxy mode, missing origin
scheme checks, URL components in Host/Origin, non-ASCII token comparison errors,
silent proxy-identity truncation, secret-bearing request logs, log injection and
duplicate security-header ambiguity. Tests include direct authorization checks
and raw HTTP duplicate-header rejection.

No deployment or native source changes. No fresh native build or sanitizer claim;
CMake/CTest prerequisites remain unavailable. LAN release is still unqualified.
Open work: actual TLS/proxy deployment, fine-grained control roles, secret rotation,
durable actor/action audit and retention, real controller rate-policy qualification,
independent witness trust/clock review, licensing and physical qualification.
