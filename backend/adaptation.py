from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

VENUE_ADAPTATION_DOCUMENT_TYPE = 'org.upp.venue-adaptation-transaction'
VENUE_ADAPTATION_SCHEMA_VERSION = 1
VENUE_PATCH_LAYER_DOCUMENT_TYPE = 'org.upp.venue-patch-layer'
VENUE_PATCH_LAYER_SCHEMA_VERSION = 1




class AdaptationRevisionConflict(RuntimeError):
    def __init__(self, expected: int, actual: int):
        super().__init__(f"venue adaptation revision conflict: expected {expected}, current {actual}")
        self.expected = expected
        self.actual = actual

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return 'sha256:' + hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def _assert_reader_safe(document: dict[str, Any], supported: int = 1) -> None:
    try:
        minimum = max(1, int(document.get('minimumReaderSchemaVersion', 1)))
    except (TypeError, ValueError):
        minimum = supported + 1
    if minimum > supported:
        raise ValueError(f"venue adaptation document requires schema reader {minimum}, this core supports {supported}")


def requirements_fingerprint(requirements: list[dict[str, Any]]) -> str:
    return fingerprint(requirements)


def plan_fingerprint(plan: dict[str, Any]) -> str:
    stable = {
        'venue': plan.get('venue'),
        'grade': plan.get('grade'),
        'readiness': plan.get('readiness'),
        'devicePlan': plan.get('devicePlan'),
        'blockers': plan.get('blockers'),
        'unmappedRequired': plan.get('unmappedRequired'),
        'discoveryWarnings': plan.get('discoveryWarnings'),
    }
    return fingerprint(stable)


def _transaction_changes(plan: dict[str, Any], requirements: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_req = {str(item.get('id')): item for item in requirements}
    changes: list[dict[str, Any]] = []
    mappings: dict[str, Any] = {}
    for item in plan.get('devicePlan', []):
        if not isinstance(item, dict):
            continue
        requirement_id = str(item.get('id', ''))
        requirement = by_req.get(requirement_id, {})
        decision = item.get('decision') if isinstance(item.get('decision'), dict) else {}
        provider = deepcopy(item.get('provider')) if isinstance(item.get('provider'), dict) else None
        patch = deepcopy(item.get('patch')) if isinstance(item.get('patch'), dict) else None
        patch_key = str(requirement.get('patchKey') or requirement_id)
        resolution = str(decision.get('status', 'blocked'))
        proposed = {
            'patchKey': patch_key,
            'target': patch.get('target') if patch else None,
            'patch': deepcopy(patch) if patch else None,
            'provider': provider,
            'capability': decision.get('capability') or decision.get('preferred'),
            'resolution': resolution,
            'quality': decision.get('quality'),
            'qualityScore': int(decision.get('qualityScore', 0) or 0),
            'timing': deepcopy(item.get('timing') or {}),
        }
        changes.append({
            'capability': str(decision.get('capability') or decision.get('preferred') or requirement.get('preferred') or requirement_id),
            'requirementId': requirement_id,
            'domain': str(requirement.get('domain', 'other')),
            'required': bool(decision.get('required', requirement.get('required', True))),
            'from': {'logicalRequirement': requirement_id},
            'to': proposed,
            'reason': 'venue compatibility resolution',
            'reversible': True,
        })
        if provider or patch:
            mappings[patch_key] = proposed
    return changes, mappings


def build_transaction(plan: dict[str, Any], requirements: list[dict[str, Any]], *, use_local_discovery: bool = False) -> dict[str, Any]:
    venue = plan.get('venue') if isinstance(plan.get('venue'), dict) else {}
    changes, mappings = _transaction_changes(plan, requirements)
    blockers = list(plan.get('blockers') or [])
    if plan.get('unmappedRequired'):
        blockers.extend(f"required venue patch unresolved: {item}" for item in plan.get('unmappedRequired') or [])
    tx_id = 'adapt-' + uuid4().hex[:16]
    return {
        'documentType': VENUE_ADAPTATION_DOCUMENT_TYPE,
        'schemaVersion': VENUE_ADAPTATION_SCHEMA_VERSION,
        'minimumReaderSchemaVersion': 1,
        'unknownFieldsPreserved': True,
        'transactionId': tx_id,
        'status': 'proposed',
        'createdAt': _now(),
        'updatedAt': _now(),
        'venueId': str(venue.get('id', 'venue')),
        'venueName': str(venue.get('name') or venue.get('id') or 'Venue'),
        'discoveryMode': 'live' if use_local_discovery else 'profile',
        'requirementsHash': requirements_fingerprint(requirements),
        'planHash': plan_fingerprint(plan),
        'grade': str(plan.get('grade', 'blocked')),
        'readiness': str(plan.get('readiness', 'blocked')),
        'changes': changes,
        'mappings': mappings,
        'departments': deepcopy(plan.get('departments') or []),
        'actions': deepcopy(plan.get('actions') or []),
        'blockers': blockers,
        'reversible': True,
        'validation': {'valid': False, 'checkedAt': None, 'blockers': blockers},
        'commit': None,
        'receipt': None,
    }


class VenueAdaptationManager:
    """Persistent transactional Venue Patch Layer.

    The active mapping is environment state. It deliberately does not rewrite
    show intent. Transactions can be validated, scheduled at a musical/cue
    boundary, committed atomically to this store, and rolled back.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._state: dict[str, Any] = {
            'revision': 1,
            'active': None,
            'transactions': {},
            'cueSequence': 0,
            'lastCue': None,
        }
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text('utf-8'))
            if isinstance(raw, dict):
                self._state = {
                    'revision': max(1, int(raw.get('revision', 1))),
                    'active': deepcopy(raw.get('active')) if isinstance(raw.get('active'), dict) else None,
                    'transactions': dict(raw.get('transactions') or {}),
                    'cueSequence': max(0, int(raw.get('cueSequence', 0))),
                    'lastCue': deepcopy(raw.get('lastCue')) if isinstance(raw.get('lastCue'), dict) else None,
                }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return

    def _persist(self) -> None:
        payload = _canonical(self._state) + '\n'
        temp = self.path.with_suffix(self.path.suffix + '.tmp')
        temp.write_text(payload, 'utf-8')
        temp.replace(self.path)

    def _touch(self) -> None:
        self._state['revision'] = int(self._state.get('revision', 1)) + 1

    def _check_revision(self, expected_revision: int | None) -> None:
        if expected_revision is None:
            return
        actual = int(self._state.get('revision', 1))
        if int(expected_revision) != actual:
            raise AdaptationRevisionConflict(int(expected_revision), actual)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            txs = [deepcopy(item) for item in self._state['transactions'].values()]
            txs.sort(key=lambda item: str(item.get('createdAt', '')), reverse=True)
            return {
                'revision': int(self._state['revision']),
                'active': deepcopy(self._state['active']),
                'transactions': txs,
                'lastCue': deepcopy(self._state['lastCue']),
            }

    def has_pending_bar_commit(self) -> bool:
        with self._lock:
            return any(
                isinstance(tx, dict) and tx.get('status') == 'pending-commit' and (tx.get('commit') or {}).get('mode') == 'next-bar'
                for tx in self._state['transactions'].values()
            )

    def get(self, transaction_id: str) -> dict[str, Any]:
        with self._lock:
            tx = self._state['transactions'].get(str(transaction_id))
            if not isinstance(tx, dict):
                raise KeyError(transaction_id)
            return deepcopy(tx)

    def attach_receipt_evidence(self, transaction_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
        """Persist signed/Public-Record evidence onto an already committed receipt."""
        with self._lock:
            tx = self._state['transactions'].get(str(transaction_id))
            if not isinstance(tx, dict):
                raise KeyError(transaction_id)
            receipt = tx.get('receipt')
            if tx.get('status') != 'committed' or not isinstance(receipt, dict):
                raise ValueError('venue adaptation receipt is not committed')
            existing = receipt.get('publicRecord')
            if isinstance(existing, dict):
                return deepcopy(tx)
            receipt['publicRecord'] = deepcopy(evidence)
            self._touch()
            self._persist()
            return deepcopy(tx)

    def propose(self, plan: dict[str, Any], requirements: list[dict[str, Any]], *, use_local_discovery: bool = False, show_venue: str = "", expected_revision: int | None = None) -> dict[str, Any]:
        tx = build_transaction(plan, requirements, use_local_discovery=use_local_discovery)
        tx['previousShowVenue'] = str(show_venue).strip()[:160] or None
        with self._lock:
            self._check_revision(expected_revision)
            active_mappings = ((self._state.get('active') or {}).get('mappings') or {}) if isinstance(self._state.get('active'), dict) else {}
            for change in tx.get('changes', []):
                to = change.get('to') if isinstance(change.get('to'), dict) else {}
                patch_key = str(to.get('patchKey') or change.get('requirementId') or '')
                previous = deepcopy(active_mappings.get(patch_key)) if patch_key in active_mappings else None
                change['from'] = previous
                change['changeType'] = 'add' if previous is None else ('unchanged' if previous == to else 'replace')
            tx['previousActiveTransactionId'] = (self._state.get('active') or {}).get('transactionId') if isinstance(self._state.get('active'), dict) else None
            self._state['transactions'][tx['transactionId']] = tx
            self._touch()
            self._persist()
            return deepcopy(tx)

    def validate(self, transaction_id: str, current_plan: dict[str, Any], requirements: list[dict[str, Any]], expected_revision: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._check_revision(expected_revision)
            tx = self._state['transactions'].get(transaction_id)
            if not isinstance(tx, dict):
                raise KeyError(transaction_id)
            _assert_reader_safe(tx, VENUE_ADAPTATION_SCHEMA_VERSION)
            blockers: list[str] = []
            if tx.get('status') in {'committed', 'rolled-back'}:
                blockers.append(f"transaction already {tx.get('status')}")
            if requirements_fingerprint(requirements) != tx.get('requirementsHash'):
                blockers.append('show requirements changed since proposal')
            if plan_fingerprint(current_plan) != tx.get('planHash'):
                blockers.append('venue compatibility plan changed since proposal')
            blockers.extend(str(item) for item in current_plan.get('blockers') or [])
            blockers.extend(f"required venue patch unresolved: {item}" for item in current_plan.get('unmappedRequired') or [])
            valid = not blockers and bool(current_plan.get('compatible')) and current_plan.get('readiness') == 'ready'
            tx['validation'] = {'valid': valid, 'checkedAt': _now(), 'blockers': sorted(set(blockers))}
            tx['status'] = 'validated' if valid else 'proposed'
            tx['updatedAt'] = _now()
            self._touch()
            self._persist()
            return deepcopy(tx)

    def schedule_commit(self, transaction_id: str, *, mode: str, show_seconds: float, bpm: float, cue_id: str = '', requested_by: str = '', expected_revision: int | None = None) -> dict[str, Any]:
        mode = str(mode or 'immediate').strip().lower()
        if mode not in {'immediate', 'next-bar', 'cue'}:
            raise ValueError('commit mode must be immediate, next-bar, or cue')
        with self._lock:
            self._check_revision(expected_revision)
            tx = self._state['transactions'].get(transaction_id)
            if not isinstance(tx, dict):
                raise KeyError(transaction_id)
            _assert_reader_safe(tx, VENUE_ADAPTATION_SCHEMA_VERSION)
            if not (tx.get('validation') or {}).get('valid'):
                raise ValueError('transaction must validate before commit')
            if tx.get('status') == 'committed':
                return deepcopy(tx)
            pending_other = [
                item.get('transactionId') for item in self._state['transactions'].values()
                if isinstance(item, dict) and item.get('status') == 'pending-commit' and item.get('transactionId') != transaction_id
            ]
            if pending_other:
                raise ValueError('another venue adaptation commit is already pending: ' + str(pending_other[0]))
            commit: dict[str, Any] = {
                'mode': mode,
                'requestedAt': _now(),
                'requestedBy': str(requested_by)[:128],
                'requestedShowSeconds': float(show_seconds),
                'targetShowSeconds': None,
                'cueId': None,
            }
            if mode == 'next-bar':
                beat_seconds = 60.0 / max(1.0, float(bpm))
                bar_seconds = beat_seconds * 4.0
                current = max(0.0, float(show_seconds))
                target = math.floor(current / bar_seconds + 1.0) * bar_seconds
                if target <= current + 1e-9:
                    target += bar_seconds
                commit['targetShowSeconds'] = round(target, 9)
            elif mode == 'cue':
                cue = str(cue_id).strip()[:128]
                if not cue:
                    raise ValueError('cue commit requires cueId')
                commit['cueId'] = cue
            tx['commit'] = commit
            tx['status'] = 'pending-commit' if mode != 'immediate' else 'validated'
            tx['updatedAt'] = _now()
            self._touch()
            self._persist()
            if mode == 'immediate':
                return self._commit_locked(tx, show_seconds=float(show_seconds), boundary={'type': 'immediate'})
            return deepcopy(tx)

    def _commit_locked(self, tx: dict[str, Any], *, show_seconds: float, boundary: dict[str, Any]) -> dict[str, Any]:
        previous = deepcopy(self._state.get('active'))
        active = {
            'documentType': VENUE_PATCH_LAYER_DOCUMENT_TYPE,
            'schemaVersion': VENUE_PATCH_LAYER_SCHEMA_VERSION,
            'minimumReaderSchemaVersion': 1,
            'unknownFieldsPreserved': True,
            'patchRevision': int((previous or {}).get('patchRevision', 0)) + 1,
            'transactionId': tx['transactionId'],
            'venueId': tx.get('venueId'),
            'venueName': tx.get('venueName'),
            'activatedAt': _now(),
            'activatedShowSeconds': round(float(show_seconds), 6),
            'grade': tx.get('grade'),
            'mappings': deepcopy(tx.get('mappings') or {}),
            'departments': deepcopy(tx.get('departments') or []),
            'discoveryMode': tx.get('discoveryMode'),
        }
        self._state['active'] = active
        tx['status'] = 'committed'
        tx['updatedAt'] = _now()
        tx['committedAt'] = active['activatedAt']
        tx['commitBoundary'] = deepcopy(boundary)
        tx['previousActive'] = previous
        tx['receipt'] = {
            'receiptId': 'receipt-' + uuid4().hex[:16],
            'reason': 'venue adaptation',
            'intentPreserved': True,
            'changes': deepcopy(tx.get('changes') or []),
            'approvedBy': [tx.get('commit', {}).get('requestedBy')] if tx.get('commit', {}).get('requestedBy') else [],
            'aiAssisted': False,
            'reversible': True,
            'transactionId': tx['transactionId'],
            'venueId': tx.get('venueId'),
            'boundary': deepcopy(boundary),
            'previousPatchRevision': (previous or {}).get('patchRevision'),
            'newPatchRevision': active['patchRevision'],
            'committedAt': active['activatedAt'],
        }
        self._touch()
        self._persist()
        return deepcopy(tx)

    def tick(self, show_seconds: float) -> list[dict[str, Any]]:
        committed: list[dict[str, Any]] = []
        with self._lock:
            due = [
                tx for tx in self._state['transactions'].values()
                if isinstance(tx, dict) and tx.get('status') == 'pending-commit'
                and (tx.get('commit') or {}).get('mode') == 'next-bar'
                and float((tx.get('commit') or {}).get('targetShowSeconds') or float('inf')) <= float(show_seconds)
            ]
            due.sort(key=lambda item: float((item.get('commit') or {}).get('targetShowSeconds') or 0.0))
            for tx in due:
                committed.append(self._commit_locked(tx, show_seconds=show_seconds, boundary={
                    'type': 'bar',
                    'targetShowSeconds': (tx.get('commit') or {}).get('targetShowSeconds'),
                    'actualShowSeconds': round(float(show_seconds), 6),
                }))
        return committed

    def trigger_cue(self, cue_id: str, show_seconds: float, expected_revision: int | None = None) -> list[dict[str, Any]]:
        cue_id = str(cue_id).strip()[:128]
        if not cue_id:
            raise ValueError('cueId required')
        committed: list[dict[str, Any]] = []
        with self._lock:
            self._check_revision(expected_revision)
            self._state['cueSequence'] = int(self._state.get('cueSequence', 0)) + 1
            self._state['lastCue'] = {'cueId': cue_id, 'sequence': self._state['cueSequence'], 'showSeconds': round(float(show_seconds), 6), 'triggeredAt': _now()}
            due = [
                tx for tx in self._state['transactions'].values()
                if isinstance(tx, dict) and tx.get('status') == 'pending-commit'
                and (tx.get('commit') or {}).get('mode') == 'cue'
                and (tx.get('commit') or {}).get('cueId') == cue_id
            ]
            for tx in due:
                committed.append(self._commit_locked(tx, show_seconds=show_seconds, boundary={'type': 'cue', 'cueId': cue_id, 'sequence': self._state['cueSequence']}))
            if not due:
                self._touch()
                self._persist()
        return committed

    def rollback(self, transaction_id: str, *, show_seconds: float, requested_by: str = '', expected_revision: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._check_revision(expected_revision)
            tx = self._state['transactions'].get(transaction_id)
            if not isinstance(tx, dict):
                raise KeyError(transaction_id)
            _assert_reader_safe(tx, VENUE_ADAPTATION_SCHEMA_VERSION)
            if tx.get('status') == 'pending-commit':
                tx['status'] = 'rolled-back'
                tx['rolledBackAt'] = _now()
                tx['rollback'] = {'requestedBy': str(requested_by)[:128], 'showSeconds': round(float(show_seconds), 6), 'cancelledPendingCommit': True}
                self._touch(); self._persist()
                return deepcopy(tx)
            if tx.get('status') != 'committed':
                raise ValueError('only committed or pending transactions can be rolled back')
            active = self._state.get('active')
            if not isinstance(active, dict) or active.get('transactionId') != transaction_id:
                raise ValueError('transaction is not the currently active venue patch layer')
            self._state['active'] = deepcopy(tx.get('previousActive'))
            tx['status'] = 'rolled-back'
            tx['rolledBackAt'] = _now()
            restored_active = tx.get('previousActive') or {}
            restored_venue_name = restored_active.get('venueName') or tx.get('previousShowVenue')
            tx['rollback'] = {
                'requestedBy': str(requested_by)[:128],
                'showSeconds': round(float(show_seconds), 6),
                'restoredTransactionId': restored_active.get('transactionId'),
                'restoredVenueName': restored_venue_name,
            }
            self._touch(); self._persist()
            return deepcopy(tx)
