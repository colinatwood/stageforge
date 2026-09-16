from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _domain_from_patch_key(patch_key: str) -> str:
    value = str(patch_key or '')
    return value.split('.', 1)[0] if '.' in value else 'other'


def _provider_key(provider: dict[str, Any] | None) -> tuple[str, str]:
    if not isinstance(provider, dict):
        return ('', '')
    return (str(provider.get('type', '')), str(provider.get('id', '')))


def _target(mapping: dict[str, Any] | None) -> str:
    if not isinstance(mapping, dict):
        return ''
    return str(mapping.get('target') or '')


@dataclass
class _Evidence:
    payload: dict[str, Any]
    observed_mono: float


class RealizationEvidenceRegistry:
    """Ephemeral adapter evidence for the active Venue Patch Layer.

    The registry never owns show or venue intent. Adapters report what they are
    actually realizing; the deterministic reconciler compares that evidence
    against the committed environment mapping.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._evidence: dict[str, _Evidence] = {}

    def report(self, data: dict[str, Any]) -> dict[str, Any]:
        patch_key = str(data.get('patchKey', '')).strip()[:160]
        if not patch_key:
            raise ValueError('patchKey required')
        payload = {
            'patchKey': patch_key,
            'providerId': str(data.get('providerId', '')).strip()[:160] or None,
            'providerType': str(data.get('providerType', '')).strip()[:64] or None,
            'target': str(data.get('target', '')).strip()[:320] or None,
            'healthy': bool(data.get('healthy', True)),
            'authorityHolder': str(data.get('authorityHolder', '')).strip()[:160] or None,
            'executionState': str(data.get('executionState', 'active')).strip()[:64] or 'active',
            'detail': deepcopy(data.get('detail')) if isinstance(data.get('detail'), dict) else {},
            'reportedAt': _now(),
        }
        with self._lock:
            self._evidence[patch_key] = _Evidence(payload, monotonic())
        return deepcopy(payload)

    def clear(self) -> None:
        with self._lock:
            self._evidence.clear()

    def snapshot(self, freshness_ms: int = 2500) -> dict[str, Any]:
        freshness_ms = max(100, min(120_000, int(freshness_ms)))
        now = monotonic()
        with self._lock:
            reports: list[dict[str, Any]] = []
            for patch_key, item in self._evidence.items():
                age_ms = max(0.0, (now - item.observed_mono) * 1000.0)
                reports.append({**deepcopy(item.payload), 'ageMs': round(age_ms, 3), 'fresh': age_ms <= freshness_ms})
        reports.sort(key=lambda item: str(item.get('patchKey', '')))
        return {'freshnessMs': freshness_ms, 'reports': reports}


def _current_rows(plan: dict[str, Any], requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_req = {str(item.get('id')): item for item in requirements if isinstance(item, dict)}
    rows: dict[str, dict[str, Any]] = {}
    for item in plan.get('devicePlan', []) or []:
        if not isinstance(item, dict):
            continue
        req_id = str(item.get('id', ''))
        req = by_req.get(req_id, {})
        patch_key = str(req.get('patchKey') or req_id)
        rows[patch_key] = item
    return rows


def evaluate_realization(
    active: dict[str, Any] | None,
    plan: dict[str, Any],
    requirements: list[dict[str, Any]],
    evidence_snapshot: dict[str, Any],
    *,
    authority: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compare committed venue intent with current compatibility and adapter evidence."""
    if not isinstance(active, dict):
        return {
            'active': False,
            'status': 'no-active-patch',
            'safeToContinue': True,
            'realized': False,
            'checkedAt': _now(),
            'mappings': [],
            'blockers': [],
            'warnings': [],
            'suggestedAction': 'none',
        }

    authority = dict(authority or {})
    current_rows = _current_rows(plan, requirements)
    evidence_by_key = {str(item.get('patchKey')): item for item in evidence_snapshot.get('reports', []) if isinstance(item, dict)}
    mappings: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    has_drift = False
    has_unverified = False

    for patch_key, expected in sorted((active.get('mappings') or {}).items()):
        expected = expected if isinstance(expected, dict) else {}
        current = current_rows.get(str(patch_key))
        decision = current.get('decision') if isinstance(current, dict) and isinstance(current.get('decision'), dict) else {}
        current_provider = current.get('provider') if isinstance(current, dict) and isinstance(current.get('provider'), dict) else None
        timing = current.get('timing') if isinstance(current, dict) and isinstance(current.get('timing'), dict) else {}
        expected_provider = expected.get('provider') if isinstance(expected.get('provider'), dict) else None
        evidence = evidence_by_key.get(str(patch_key))
        domain = _domain_from_patch_key(str(patch_key))
        patch_doc = expected.get('patch') if isinstance(expected.get('patch'), dict) else {}
        expected_authority = (
            authority.get(str(patch_key))
            or authority.get(domain)
            or str(patch_doc.get('authority', '')).strip()
            or str(expected.get('authority', '')).strip()
            or None
        )

        status = 'compatible'
        reasons: list[str] = []
        if current is None:
            status = 'blocked'
            reasons.append('current venue plan no longer contains this mapping')
        elif decision.get('status') == 'blocked' or timing.get('status') == 'blocked' or current_provider is None:
            status = 'blocked'
            reasons.append('current venue provider or timing is unavailable')
        else:
            if _provider_key(current_provider) != _provider_key(expected_provider):
                status = 'drift'
                reasons.append('resolved provider changed since commit')
            current_patch = current.get('patch') if isinstance(current.get('patch'), dict) else None
            if _target(current_patch) and _target(expected) and _target(current_patch) != _target(expected):
                status = 'drift'
                reasons.append('venue patch target changed since commit')

        realized = False
        evidence_status = 'unverified'
        if evidence is None or not evidence.get('fresh'):
            has_unverified = True
            reasons.append('fresh execution evidence unavailable')
        else:
            evidence_status = 'healthy' if evidence.get('healthy') else 'unhealthy'
            if not evidence.get('healthy'):
                status = 'blocked'
                reasons.append('execution adapter reports unhealthy realization')
            expected_provider_id = str((expected_provider or {}).get('id') or '')
            if evidence.get('providerId') and expected_provider_id and str(evidence.get('providerId')) != expected_provider_id:
                status = 'drift'
                reasons.append('execution provider differs from committed provider')
            if evidence.get('target') and _target(expected) and str(evidence.get('target')) != _target(expected):
                status = 'drift'
                reasons.append('execution target differs from committed target')
            if expected_authority and evidence.get('authorityHolder') and str(evidence.get('authorityHolder')) != expected_authority:
                status = 'blocked'
                reasons.append('authority holder differs from committed ownership')
            realized = status == 'compatible' and bool(evidence.get('healthy'))

        if status == 'blocked':
            blockers.append(f'{patch_key}: ' + '; '.join(reasons))
        elif status == 'drift':
            has_drift = True
            warnings.append(f'{patch_key}: ' + '; '.join(reasons))
        elif not realized:
            warnings.append(f'{patch_key}: ' + '; '.join(reasons))

        mappings.append({
            'patchKey': str(patch_key),
            'domain': domain,
            'expected': deepcopy(expected),
            'currentProvider': deepcopy(current_provider),
            'currentTiming': deepcopy(timing),
            'status': status,
            'realized': realized,
            'evidenceStatus': evidence_status,
            'evidence': deepcopy(evidence),
            'expectedAuthority': expected_authority,
            'reasons': reasons,
        })

    if blockers:
        overall = 'blocked'
        suggested = 'rollback-or-repair'
    elif has_drift:
        overall = 'drift'
        suggested = 'propose-repair'
    elif has_unverified:
        overall = 'unverified'
        suggested = 'verify-execution'
    else:
        overall = 'realized'
        suggested = 'none'

    return {
        'active': True,
        'transactionId': active.get('transactionId'),
        'patchRevision': active.get('patchRevision'),
        'venueId': active.get('venueId'),
        'venueName': active.get('venueName'),
        'status': overall,
        'safeToContinue': not bool(blockers),
        'realized': overall == 'realized',
        'checkedAt': _now(),
        'planReadiness': plan.get('readiness'),
        'planGrade': plan.get('grade'),
        'mappings': mappings,
        'blockers': blockers,
        'warnings': warnings,
        'suggestedAction': suggested,
    }
