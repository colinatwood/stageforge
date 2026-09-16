# Sol checkpoint 7

Fixed audio endpoint ID reuse overwriting saved identity. Both discovery selection
and activation lookup now use the same identity resolver. Duplicate serial matches
are rejected even when one occupies the original ID. Empty/malformed ALSA addresses
remain volatile instead of crashing or accepting a partial address.

Validation: 372 Python tests passed without skips with the qualification native
engine selected. Four new regressions cover repeated scans, persistence across
restart, duplicate serials and malformed addresses. Native code was unchanged;
CMake/CTest remain unavailable in this session. No hardware qualification claimed.

Remaining Sol work: scan/activation serialization and hotplug lifecycle fixes;
explicit identity replacement UX; actual audio parameters and conversion policy;
DAW temporary-resource observability. Astra review: authority recovery, live audio
architecture and final security threat model. Equipment/host-dependent qualification
remains deferred or blocked as documented in current-backlog.md.
