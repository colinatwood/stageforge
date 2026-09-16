# Astra backlog checkpoint 45 validation

Checkpoint 45 generalizes the existing Venue Patch Layer authority-lease primitive into typed department/resource authority leases while preserving the original venue reconciliation behavior and cluster-authority fence.

## Typed authority scopes

Authority leases now carry an explicit `scopeKind`:

- `patch` — one exact active Venue Patch Layer mapping such as `audio.foh`;
- `department` — one known operational department such as `audio`, `lighting`, `midi`, `notation`, `production`, `show`, `system` or `technology`;
- `resource` — one exact runtime resource revision key such as `audio`, `lighting-network`, `handoff`, `technology`, `midi-bindings`, `monitor:<player>`, `midi:<player>` or `notation:<player>`.

Scope kind is part of conflict identity. A resource named `audio` and the `audio` department are distinct scopes. Regranting the same typed scope replaces its prior holder visibly; it does not stack two active holders.

Runtime resolution is deterministic: an exact resource lease wins over the resource's department lease, then the caller-provided default applies. Unknown explicit resources/departments fail closed rather than creating inert or typo-derived authority.

## Lifecycle context

Lease lifecycle is separate from scope kind:

- `venue` context preserves the legacy patch/domain behavior and is invalidated whenever the active Venue Patch Layer commits or rolls back;
- `runtime` context is used by explicit generalized resource/department leases and survives venue remapping.

All operational leases remain ephemeral. Losing node authority fences physical outputs and clears the lease registry, so a promoted/recovered node must reacquire scoped ownership explicitly. Promotion never restores physical outputs or operational leases automatically.

Legacy requests that omit `scopeKind` remain compatible: an active patch key resolves to a venue `patch` lease and an active patch domain resolves to a venue `department` lease.

## Audit and reconciliation

Grant/revoke operations continue through the authority-role HTTP boundary and are recorded in the existing durable external event journal. Audit payloads now include `scopeKind` and `context` as well as scope, grantee and expiry metadata.

Venue reconciliation keeps its existing exact-patch/domain lookup. Active typed patch and department leases are projected into that compatibility map, while resource leases remain available through explicit runtime resource-authority resolution and cannot accidentally masquerade as venue patch keys.

These leases do not grant witness quorum authority and do not bypass `_has_authority()`. They describe bounded operational ownership only; cluster-primary/witness authority remains the prerequisite for granting or revoking them.

## Validation

- Release Python suite against the checkpoint-44 RT-qualified engine: **540 tests passed**.
- Focused authority/reconciliation group: **15 tests passed**, covering typed conflict identity, exact-resource precedence, expiry, venue-context invalidation, runtime-context preservation, audit evidence, legacy reconciliation and node demotion.
- Existing HTTP venue-authority integration was extended to grant and inspect a generalized `resource` lease through the public API.
- Native source is unchanged from checkpoint 44; RT native CTest remains **2/2 passed**.
- Automation performance passed with 4096 points / 8192 frames.
- Public JSON schemas: **118** parsed successfully; `frontend/openapi.json` parsed successfully.
- Frontend JavaScript: **7/7** files passed `node --check`.

## Remaining boundary

The generalized lease API still uses the historical `/api/v1/venue/authority` route family for backward compatibility. It is operational authority metadata, not an identity credential and not a substitute for API roles, adapter credentials, witness quorum or physical-output arming.

Checkpoint 45 does not yet sign or externally witness authority/adaptation receipts. That is the next local software seam before governance/Public Record work can rely on independently verifiable operational evidence.
