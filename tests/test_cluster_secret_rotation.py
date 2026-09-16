import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from cluster_secrets import RotatingHmacKeyring
from planned_handoff import make_offer, make_ready_receipt, verify_offer, verify_ready_receipt
from replication import make_envelope, verify_envelope
from witness import WitnessQuorumClient, sign_response

OLD = "o" * 40
NEW = "n" * 40


def write_keyring(path: Path, active: str, keys: dict[str, str]) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"version": 1, "activeKeyId": active, "keys": keys}, separators=(",", ":")), "utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)


class ClusterSecretRotationTests(unittest.TestCase):
    def test_keyring_reloads_atomically_and_removed_key_is_not_retained(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "cluster-keys.json"
            write_keyring(path, "old", {"old": OLD, "new": NEW})
            ring = RotatingHmacKeyring(path)
            first = ring.snapshot()
            self.assertEqual(first.active_key_id, "old")
            self.assertEqual(first.resolve("old"), OLD.encode())
            write_keyring(path, "new", {"old": OLD, "new": NEW})
            self.assertEqual(ring.snapshot().active_key_id, "new")
            write_keyring(path, "new", {"new": NEW})
            with self.assertRaisesRegex(PermissionError, "unknown"):
                ring.snapshot().resolve("old")
            # A previously pinned operation snapshot remains immutable.
            self.assertEqual(first.resolve("old"), OLD.encode())

    def test_private_regular_file_is_required(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "cluster-keys.json"
            write_keyring(path, "old", {"old": OLD})
            os.chmod(path, 0o644)
            with self.assertRaises(PermissionError):
                RotatingHmacKeyring(path)
            os.chmod(path, 0o600)
            link = Path(raw) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(PermissionError):
                RotatingHmacKeyring(link)

    def test_malformed_replacement_fails_next_operation_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "cluster-keys.json"
            write_keyring(path, "old", {"old": OLD})
            ring = RotatingHmacKeyring(path)
            path.write_text('{"version":1,"activeKeyId":"old","activeKeyId":"new","keys":{}}', "utf-8")
            os.chmod(path, 0o600)
            with self.assertRaises(PermissionError):
                ring.snapshot()

    def test_replication_overlap_switch_and_downgrade_rejection(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "cluster-keys.json"
            write_keyring(path, "old", {"old": OLD, "new": NEW})
            ring = RotatingHmacKeyring(path)
            old_auth = ring.snapshot()
            old_envelope = make_envelope(
                {"revision": 1}, node_id="a", epoch=1, sequence=1,
                secret=old_auth.active_secret, key_id=old_auth.active_key_id,
            )
            self.assertEqual(old_envelope["keyId"], "old")
            self.assertEqual(verify_envelope(old_envelope, keyset=ring.snapshot()), (True, "ok"))

            write_keyring(path, "new", {"old": OLD, "new": NEW})
            new_auth = ring.snapshot()
            new_envelope = make_envelope(
                {"revision": 2}, node_id="a", epoch=1, sequence=2,
                secret=new_auth.active_secret, key_id=new_auth.active_key_id,
            )
            self.assertEqual(new_envelope["keyId"], "new")
            self.assertEqual(verify_envelope(old_envelope, keyset=ring.snapshot()), (True, "ok"))
            self.assertEqual(verify_envelope(new_envelope, keyset=ring.snapshot()), (True, "ok"))

            legacy = make_envelope({"revision": 3}, node_id="a", epoch=1, sequence=3, secret=OLD.encode())
            ok, reason = verify_envelope(legacy, keyset=ring.snapshot())
            self.assertFalse(ok)
            self.assertIn("identifier", reason)

            write_keyring(path, "new", {"new": NEW})
            ok, reason = verify_envelope(old_envelope, keyset=ring.snapshot())
            self.assertFalse(ok)
            self.assertIn("unknown", reason)
            self.assertEqual(verify_envelope(new_envelope, keyset=ring.snapshot()), (True, "ok"))

    def test_planned_handoff_finishes_under_offer_key_or_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "cluster-keys.json"
            write_keyring(path, "old", {"old": OLD, "new": NEW})
            ring = RotatingHmacKeyring(path)
            auth = ring.snapshot()
            offer = make_offer(
                transaction_id=7, source_node_id="a", target_node_id="b", source_epoch=2,
                target_epoch=3, target_show_ns=10, allow_degraded_program=False,
                secret=auth.active_secret, key_id=auth.active_key_id,
            )
            write_keyring(path, "new", {"old": OLD, "new": NEW})
            self.assertEqual(verify_offer(offer, keyset=ring.snapshot(), expected_target_node_id="b"), (True, "ok"))
            pinned = ring.snapshot().resolve(offer["keyId"])
            receipt = make_ready_receipt(offer=offer, program_ready=True, secret=pinned, key_id=offer["keyId"])
            self.assertEqual(
                verify_ready_receipt(receipt, keyset=ring.snapshot(), expected_source_node_id="a", offer=offer),
                (True, "ok"),
            )
            write_keyring(path, "new", {"new": NEW})
            ok, reason = verify_ready_receipt(receipt, keyset=ring.snapshot(), expected_source_node_id="a", offer=offer)
            self.assertFalse(ok)
            self.assertIn("unknown", reason)

    def test_witness_quorum_pins_one_key_snapshot_per_operation(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "witness-keys.json"
            write_keyring(path, "old", {"old": OLD, "new": NEW})
            ring = RotatingHmacKeyring(path)
            client = WitnessQuorumClient(["http://a", "http://b", "http://c"], "show", "node", b"", keyring=ring)
            seen = []

            def reply(request, **kwargs):
                body = json.loads(request.data)
                seen.append(body["keyId"])
                secret = OLD.encode() if body["keyId"] == "old" else NEW.encode()
                if len(seen) == 1:
                    write_keyring(path, "new", {"old": OLD, "new": NEW})
                result = {
                    "granted": True, "clusterId": "show", "holderNodeId": "node",
                    "epoch": 1, "expiresAtUnixMs": 9999999999999,
                }
                response = MagicMock()
                response.__enter__.return_value.read.return_value = json.dumps(
                    sign_response(result, body, "acquire", secret, key_id=body["keyId"])
                ).encode()
                return response

            with patch("witness.urlopen", side_effect=reply):
                self.assertTrue(client.acquire()["leaseValid"])
                self.assertEqual(seen, ["old", "old", "old"])
                seen.clear()
                self.assertTrue(client.acquire()["leaseValid"])
                self.assertEqual(seen, ["new", "new", "new"])


    def test_production_witness_server_rotates_without_restart_and_rejects_legacy_downgrade(self):
        from http.server import ThreadingHTTPServer
        from threading import Thread
        import witness_server
        from witness import WitnessLeaseStore
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "witness-keys.json"
            write_keyring(path, "old", {"old": OLD, "new": NEW})
            ring = RotatingHmacKeyring(path)
            with patch.object(witness_server, "KEYRING", ring), patch.object(witness_server, "SECRET", b""), patch.object(witness_server, "STORE", WitnessLeaseStore()):
                server = ThreadingHTTPServer(("127.0.0.1", 0), witness_server.Handler)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    url = f"http://127.0.0.1:{server.server_port}"
                    client = WitnessQuorumClient([url], "show", "node", b"", keyring=ring)
                    self.assertTrue(client.acquire()["leaseValid"])
                    write_keyring(path, "new", {"old": OLD, "new": NEW})
                    self.assertTrue(client.acquire()["leaseValid"])
                    write_keyring(path, "new", {"new": NEW})
                    self.assertTrue(client.acquire()["leaseValid"])
                    legacy = WitnessQuorumClient([url], "show", "node", OLD.encode())
                    self.assertFalse(legacy.acquire()["leaseValid"])
                finally:
                    server.shutdown(); thread.join(timeout=2); server.server_close()

    def test_witness_keyring_mode_never_falls_back_to_legacy_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "witness-keys.json"
            write_keyring(path, "new", {"new": NEW})
            ring = RotatingHmacKeyring(path, OLD.encode())
            auth = ring.snapshot()
            with self.assertRaisesRegex(PermissionError, "identifier"):
                auth.resolve(None)
            with self.assertRaisesRegex(PermissionError, "unknown"):
                auth.resolve("old")


if __name__ == "__main__":
    unittest.main()
