# Authenticated witness replies

Acquisition and transfer replies now carry `responseVersion: 1`, `operation`,
`requestDigest`, and `responseHmacSha256`. The digest covers the exact unsigned
request including its nonce. The HMAC covers every response field except the
signature, wrapped with purpose `org.upp.witness-response/1` for domain separation.
Requests retain protocolVersion 1.

Clients verify authentication and exact request/operation binding before parsing
grants. Existing cluster, holder, epoch, expiry, transaction and quorum checks
remain. Unsigned, altered, wrong-key or replayed responses become denied results.
Both grants and denials are signed after request authentication. HTTP errors
never count as grants. Status/health GET replies remain informational only.

## Upgrade order

Update witness servers first, then node clients. Old clients tolerate the extra
fields; new clients reject unsigned replies from old servers. There is no unsigned
fallback. Check a quorum of updated witnesses before relying on a new client.
Failed renewal cannot extend an existing lease. Failed transfer still leaves the
source fenced under the existing handoff policy. This update never clears a fence.

## Trust boundary

The existing shared witness secret authenticates replies. Anyone possessing it
can forge replies; this does not isolate compromised cluster members or prove
witness independence. Distinct URLs are not proof of independent hosts. This
increment adds no TLS, key rotation, per-witness keys, request replay storage or
cross-host clock uncertainty bounds. Fresh request binding prevents reuse of a
captured reply for a different request.

## Backlog state and testing

Physical hardware qualification is deferred at the user's request. Reply authentication is also used by the fenced-node recovery protocol. A recovering source submits the exact persisted transfer facts, SHA-256 fence identity, recovery ID and fresh nonce. Each witness authorizes only when its current durable lease still records that exact transfer to the named target. A quorum response permits the client to persist a recovery receipt, re-check the fence inode and digest, and then remove it. Recovery clears acquisition suspension but caches no lease, keeps the runtime standby and never restores physical authority.

Manual fence deletion remains unsupported. Malformed, swapped, stale or quorum-unverifiable evidence stays fenced.

Tests cover signed grants/denials, malformed authenticated fields, unsigned and
tampered replies, wrong keys, nonce/operation mismatches, and loopback HTTP
acquisition/transfer/recovery through the production handler. No hardware is involved.

The full Python suite passed all 334 tests with no skips against the existing
qualification-enabled native build. Native source and ABI were unchanged.
See `current-backlog.md` for the remaining software priorities and deferred testing.
