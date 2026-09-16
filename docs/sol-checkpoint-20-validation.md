# Sol backlog checkpoint 20 validation

Checkpoint 20 adds quorum-authorized recovery for nodes persistently fenced by planned authority transfer.

## Safety contract

- Recovery requires explicit `acknowledgeStandbyRecovery: true` and a bounded recovery ID.
- The persisted fence must be a bounded regular non-symbolic file whose cluster and source node match the client.
- Requests bind the exact source/target nodes, epochs, transfer transaction, fence digest, recovery ID and fresh nonce.
- Each witness authorizes only while its durable lease records that exact transfer and target epoch.
- Every reply is authenticated and bound to its individual request.
- Fewer than quorum approvals leave the fence and acquisition suspension unchanged.
- A quorum result is durably recorded before fence removal.
- The fence inode and SHA-256 digest are rechecked immediately before unlink.
- Successful recovery clears suspension but caches no lease, forces standby and keeps all physical authority fenced.

## Qualification boundary

The software protocol does not prove witness-host independence, TLS availability or cross-host clock safety. A corrupt or stale fence that cannot obtain exact quorum authorization intentionally requires an offline incident process.

## Recorded result

- 415 Python tests passed.
- Native streaming/transaction tests and current-ABI smoke passed.
- Frontend syntax and production-panel tests passed.
- OpenAPI and all 117 JSON schemas parsed successfully.

The Python suite's separate sanitizer prerequisite probe cannot find `cmake` and `ctest` in its process environment, so that environment-gated release check was not counted as executed.
