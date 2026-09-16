from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4


_SCOPE_KINDS = {"patch", "department", "resource"}
_CONTEXTS = {"venue", "runtime"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class AuthorityLeaseRegistry:
    """Ephemeral, fail-closed authority leases for typed operational scopes.

    Scope type and lifecycle context are intentionally separate. A department
    lease can be venue-local (legacy Venue Patch Layer behavior) or runtime-wide.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._leases: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        with self._lock:
            self._leases.clear()

    def clear_context(self, context: str) -> int:
        context = str(context).strip().lower()
        if context not in _CONTEXTS:
            raise ValueError("authority lease context must be venue or runtime")
        cleared = 0
        with self._lock:
            for item in self._leases.values():
                if item.get("context") != context or not self._is_active(item):
                    continue
                item["revoked"] = True
                item["revokedAt"] = _now()
                item["revokedBy"] = "context-change"
                cleared += 1
        return cleared

    @staticmethod
    def _clean(value: Any, limit: int) -> str:
        text = str(value or "").strip()[:limit]
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
            raise ValueError("authority lease identifiers cannot contain control characters")
        return text

    def grant(self, data: dict[str, Any]) -> dict[str, Any]:
        scope = self._clean(data.get('scope'), 160)
        grantee = self._clean(data.get('grantee'), 160)
        granted_by = self._clean(data.get('grantedBy'), 160)
        reason = self._clean(data.get('reason'), 320)
        scope_kind = self._clean(data.get('scopeKind', 'department'), 24).lower()
        context = self._clean(data.get('context', 'venue'), 24).lower()
        if not scope or not grantee:
            raise ValueError('authority lease requires scope and grantee')
        if scope_kind not in _SCOPE_KINDS:
            raise ValueError('authority lease scopeKind must be patch, department, or resource')
        if context not in _CONTEXTS:
            raise ValueError('authority lease context must be venue or runtime')
        try:
            ttl = float(data.get('ttlSeconds', 300.0))
        except (TypeError, ValueError) as exc:
            raise ValueError('ttlSeconds must be numeric') from exc
        ttl = max(1.0, min(43_200.0, ttl))
        lease_id = 'lease-' + uuid4().hex[:16]
        with self._lock:
            # Conflict identity is typed. A resource called "audio" and the
            # audio department are intentionally different authority scopes.
            for lease in self._leases.values():
                if (lease.get('scopeKind') == scope_kind and lease.get('scope') == scope
                        and self._is_active(lease)):
                    lease['revoked'] = True
                    lease['revokedAt'] = _now()
                    lease['replacedBy'] = lease_id
            item = {
                'leaseId': lease_id,
                'scopeKind': scope_kind,
                'scope': scope,
                'context': context,
                'grantee': grantee,
                'grantedBy': granted_by or None,
                'reason': reason or None,
                'issuedAt': _now(),
                'ttlSeconds': ttl,
                'revoked': False,
                '_expiresMono': monotonic() + ttl,
            }
            self._leases[lease_id] = item
            return self._public(item)

    def revoke(self, lease_id: str, requested_by: str = '') -> dict[str, Any]:
        with self._lock:
            item = self._leases.get(str(lease_id))
            if not item:
                raise KeyError(lease_id)
            if not item.get('revoked'):
                item['revoked'] = True
                item['revokedAt'] = _now()
                item['revokedBy'] = self._clean(requested_by, 160) or None
            return self._public(item)

    @staticmethod
    def _is_active(item: dict[str, Any]) -> bool:
        return not item.get('revoked') and float(item.get('_expiresMono', 0.0)) > monotonic()

    def _public(self, item: dict[str, Any]) -> dict[str, Any]:
        remaining = max(0.0, float(item.get('_expiresMono', 0.0)) - monotonic())
        active = not item.get('revoked') and remaining > 0.0
        return {k: deepcopy(v) for k, v in item.items() if not k.startswith('_')} | {
            'active': active,
            'remainingSeconds': round(remaining, 3),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            leases = [self._public(item) for item in self._leases.values()]
        leases.sort(key=lambda item: str(item.get('issuedAt', '')), reverse=True)
        active = [item for item in leases if item.get('active')]
        return {
            'leases': leases,
            'active': active,
            'activeByKind': {
                kind: [item for item in active if item.get('scopeKind') == kind]
                for kind in sorted(_SCOPE_KINDS)
            },
        }

    def authority_map(self) -> dict[str, str]:
        """Compatibility map for Venue Patch Layer reconciliation.

        Patch and department leases use their raw scope names so the existing
        exact-patch then domain resolution remains unchanged.
        """
        result: dict[str, str] = {}
        for item in reversed(self.snapshot()['active']):
            if item.get('scopeKind') in {'patch', 'department'}:
                result[str(item['scope'])] = str(item['grantee'])
        return result

    def resolve(self, resource: str, department: str = '', default: str | None = None) -> str | None:
        resource = self._clean(resource, 160)
        department = self._clean(department, 160)
        active = self.snapshot()['active']
        # Exact resource ownership is more specific than department ownership.
        for kind, scope in (("resource", resource), ("department", department)):
            if not scope:
                continue
            for item in active:
                if item.get('scopeKind') == kind and item.get('scope') == scope:
                    return str(item.get('grantee'))
        return default


# Backward-compatible import name for integrations that adopted the Venue Patch
# Layer API before authority scopes were generalized.
VenueAuthorityLeaseRegistry = AuthorityLeaseRegistry
