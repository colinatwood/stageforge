# Authenticated Planned-Handoff Peer Readiness

The standby now reports execution-backed pre-roll readiness to the primary that created the planned-handoff offer. This closes the coordination gap where readiness previously existed only in the standby process.

## Flow

1. The primary creates a signed offer fixing the transaction, source and target nodes, authority epochs, Show-Time boundary and degraded-program policy.
2. The standby verifies and prepares the native handoff transaction.
3. An operator acknowledges pre-roll only after the deterministic handoff decision consumes fresh renderer and live-feed evidence.
4. The standby acknowledges the native transaction, signs a `target-ready` receipt and posts it to the configured peer's `/api/v1/handoff/planned/peer-ready` route.
5. The primary verifies the receipt against its current offer and moves that offer to `target-ready`.
6. At the offered Show-Time boundary, the old primary explicitly self-fences and sends a signed transfer request to every witness. Each witness atomically changes the live lease from the exact source node/epoch to the offer's target node/next epoch.
7. The standby acquires the transferred lease and commits its native transaction against that exact epoch.

An exact receipt can be delivered again safely. A receipt with conflicting readiness is rejected after the first receipt is accepted.

## Security and fencing

The receipt is canonical JSON authenticated with the replication HMAC secret. Its digest covers protocol and receipt types, transaction identity, both node identities, source and target epochs, target Show Time, the boolean program-readiness result and receipt issue time. The receiver also rejects a receipt issued before the matching offer. `programReady` must be an actual JSON boolean; truthy strings are not accepted.

The HTTP route does not replace cryptographic authentication and it does not arm physical outputs. Deployments should use TLS or a protected show-control network to keep metadata confidential and protect availability.

## Failure behavior and observability

Readiness delivery is synchronous and bounded by the peer client's configured timeout. The standby retains its local `target-ready` state when delivery fails and exposes the result under `readinessDelivery`. Peer status includes readiness attempts, deliveries, failures and the last delivery error, allowing an operator or coordinator to retry the acknowledgement safely.

Witness transfer has no generic unowned or unlocked state, so an unrelated node cannot race the intended standby. Exact transaction retries are idempotent and do not extend the transferred lease. The client serializes renewal and transfer calls, clears its cached authority before transfer, and the runtime demotes plus fences physical outputs before the first irreversible witness request.

If fewer than a quorum transfer, the result is `release-indeterminate`. The old primary remains demoted because accepted witness transfers cannot be safely rolled back. The intended standby still cannot become authoritative without acquiring a quorum at the exact target epoch. This deliberately trades availability for split-brain safety.

After a transfer attempt, `acquisitionSuspended=true` prevents that witness client
from acquiring or renewing authority for the remainder of its lifetime, even if
the target lease later expires. Automatic failover cannot bypass this fence.
The runtime serializes its background renewal/role-change tick with planned
authority release; these are control-thread operations, not audio callbacks.

Starting with Core 5.10.3, the runtime supplies a local
`handoff-acquisition-fence.json` marker in the node data directory. The client
creates it exclusively and syncs its contents and parent directory before any
witness transfer request. Failure to persist prevents transfer. Marker presence
is sufficient to fence startup; incomplete contents, symlinks or inspection
errors never count as an unfenced node.

The runtime starts a fenced node as standby even if witness URLs were removed.
Ordinary promotion, automatic failover and force-role overrides cannot clear
the fence. An explicitly authorized rejoin/recovery protocol remains backlog
work. Preserve the node data directory across restarts: this mechanism does not
protect against deleted, rolled-back or replaced storage. Standalone clients
without a fence path retain process-local suspension only.

Core 5.10.2 validation: all 307 Python tests passed against the existing directly
compiled native engine. Native code was unchanged. CMake/CTest remain unavailable
in this environment, so a fresh full release-gate pass is still pending.

Core 5.10.3 validation: all 311 Python tests passed against the same native engine,
including four new persistence/startup regressions. Native code remains unchanged;
the full CMake/CTest release gate remains pending.

Core 5.10.4 validates witness response types and binds grants to the requested
cluster, holder and (for transfer) transaction. Responses that have expired by
the end of collection cannot count toward a fresh quorum. Duplicate endpoint
URLs, ignoring trailing slashes, are rejected at configuration time. This does
not establish that different DNS names point to independent witnesses; deployment
qualification must verify independence. Response validation at that checkpoint did not add response
signatures or solve cross-host clock uncertainty. Authorized rejoin remains pending.

The subsequent [response authentication increment](witness-response-authentication.md)
adds mandatory request-bound signatures. Cross-host clock uncertainty and authorized
rejoin remain unfinished. Physical qualification is deferred for lack of equipment.

Validation: 316 Python tests passed against a freshly compiled native engine.
The five new regressions exercise malformed grants, duplicate configuration,
transaction mismatch and expiry during collection. CMake/CTest are still absent,
so the full release gate remains pending.
