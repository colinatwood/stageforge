# Astra checkpoint 30 validation

467 Python tests passed on 2026-09-13. Seven new tests cover private file loading,
environment fallback removal, forced authentication, atomic replacement, pinned
request snapshots, malformed updates, symlinks, permissions, size/schema limits,
role overlap, duplicate keys and real keep-alive HTTP rotation.

The HTTP test replaces the credential file between requests on one connection,
accepts the replacement credential and rejects the old credential. Health payload
is stubbed; credential reading and HTTP handling are real.

No secrets were provisioned and no live configuration was changed. Rotation applies
to subsequent requests, not in-flight work or existing SSE streams. Trusted parent
directories and atomic replacement remain operator requirements. HTTP file mode
does not rotate witness/replication credentials. No native source changes or fresh
native/sanitizer build; CMake/CTest prerequisites remain unavailable.

Remaining: immediate session revocation, per-user roles, durable actor/action audit,
TLS/proxy deployment, controller workload and physical qualification.
