import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.persistence import StateRepository


class AuthorizationAuditRotationTests(unittest.TestCase):
    def repository(self, root, rotate=900, retain=2):
        repository = StateRepository(Path(root))
        # Production configuration enforces a 64 KiB minimum. Tests shrink the
        # threshold after construction so rotation behavior is exercised quickly.
        repository.authorization_audit_rotate_bytes = rotate
        repository.authorization_audit_retain_segments = retain
        return repository

    def event(self, number):
        return {
            "type": "http-authorization",
            "timestampNs": number,
            "actor": f"operator-{number}",
            "roles": ["operator"],
            "method": "POST",
            "action": "show.control",
            "target": None,
            "decision": "allow",
            "reason": "operator-role",
            "padding": "x" * 120,
        }

    def append_until_segments(self, repository, count, minimum_segments):
        for number in range(count):
            repository.append_authorization_audit(self.event(number))
            if len(list(repository.authorization_audit_segments.glob("*.jsonl"))) >= minimum_segments:
                return number + 1
        self.fail(f"did not create {minimum_segments} segments")

    def test_rotation_and_retention_keep_one_verifiable_chain(self):
        with tempfile.TemporaryDirectory() as raw:
            repository = self.repository(raw, retain=2)
            total = 16
            for number in range(total):
                repository.append_authorization_audit(self.event(number))
            result = repository.verify_authorization_audit()
            self.assertTrue(result["ok"], result)
            self.assertLessEqual(result["retainedSegments"], 2)
            self.assertGreater(result["prunedSegments"], 0)
            self.assertGreater(result["prunedRecords"], 0)
            self.assertNotEqual(result["retentionAnchor"], "0" * 64)
            self.assertEqual(result["records"] + result["prunedRecords"], total)
            self.assertLessEqual(result["activeBytes"], repository.authorization_audit_rotate_bytes)

    def test_tampering_retained_segment_breaks_verification(self):
        with tempfile.TemporaryDirectory() as raw:
            repository = self.repository(raw, retain=4)
            self.append_until_segments(repository, 12, 1)
            segment = sorted(repository.authorization_audit_segments.glob("*.jsonl"))[0]
            lines = segment.read_text("utf-8").splitlines()
            record = json.loads(lines[0])
            record["event"]["actor"] = "tampered"
            lines[0] = json.dumps(record, sort_keys=True, separators=(",", ":"))
            segment.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = repository.verify_authorization_audit()
            self.assertFalse(result["ok"])
            self.assertIn("hash", result["error"])

    def test_failed_retention_anchor_write_prunes_nothing(self):
        with tempfile.TemporaryDirectory() as raw:
            repository = self.repository(raw, retain=1)
            self.append_until_segments(repository, 12, 1)
            # Fill the next active segment until the second rotation attempts to
            # prune. ENOSPC at the anchor write must leave both segments present.
            with patch.object(repository, "_atomic_write_json", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    for number in range(100, 120):
                        repository.append_authorization_audit(self.event(number))
            self.assertGreaterEqual(len(list(repository.authorization_audit_segments.glob("*.jsonl"))), 2)
            result = repository.verify_authorization_audit()
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["prunedSegments"], 0)

    def test_crash_after_anchor_commit_keeps_chain_valid_and_residue_reclaimable(self):
        with tempfile.TemporaryDirectory() as raw:
            repository = self.repository(raw, retain=1)
            self.append_until_segments(repository, 12, 1)
            original_unlink = Path.unlink
            failed = {"done": False}
            def crash_once(path, *args, **kwargs):
                if path.parent == repository.authorization_audit_segments and not failed["done"]:
                    failed["done"] = True
                    raise OSError("simulated crash after anchor")
                return original_unlink(path, *args, **kwargs)
            with patch.object(Path, "unlink", crash_once):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    for number in range(200, 220):
                        repository.append_authorization_audit(self.event(number))
            result = repository.verify_authorization_audit()
            self.assertTrue(result["ok"], result)
            self.assertGreater(result["prunedSegments"], 0)
            self.assertGreater(result["stalePrunedFiles"], 0)
            repository._prune_authorization_segments()
            result = repository.verify_authorization_audit()
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["stalePrunedFiles"], 0)

    def test_steady_state_append_uses_cached_head_not_full_chain_scan(self):
        with tempfile.TemporaryDirectory() as raw:
            repository = self.repository(raw, rotate=10_000, retain=2)
            repository.append_authorization_audit(self.event(1))
            with patch.object(repository, "_scan_authorization_audit",
                              side_effect=AssertionError("unexpected full scan")):
                repository.append_authorization_audit(self.event(2))
            result = repository.verify_authorization_audit()
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["records"], 2)


if __name__ == "__main__":
    unittest.main()
