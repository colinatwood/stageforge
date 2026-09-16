import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from witness import WitnessQuorumClient, WitnessResult, sign_response


class WitnessResponseValidationTests(unittest.TestCase):
    def test_duplicate_configuration_is_rejected_without_reducing_quorum(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            WitnessQuorumClient(["http://a", "http://a/", "http://b"], "show", "node", b"key")

    def test_invalid_network_grants_are_denied_without_raising(self):
        client = WitnessQuorumClient(["http://a"], "show", "node", b"key")
        valid = {"granted": True, "clusterId": "show", "holderNodeId": "node", "epoch": 1, "expiresAtUnixMs": 9999999999999}
        cases = [[], None, {**valid, "granted": "false"}, {**valid, "epoch": True},
                 {**valid, "expiresAtUnixMs": "9999999999999"},
                 {**valid, "clusterId": "other"}, {**valid, "holderNodeId": "other"}]
        for raw in cases:
            with self.subTest(raw=raw):
                response = MagicMock()
                def reply(request, **kwargs):
                    payload = json.loads(request.data)
                    signed = sign_response(raw, payload, "acquire", b"key") if isinstance(raw, dict) else raw
                    response.__enter__.return_value.read.return_value = json.dumps(signed).encode()
                    return response
                with patch("witness.urlopen", side_effect=reply):
                    result = client._one("http://a")
                self.assertFalse(result.granted)
                self.assertIsNotNone(result.error)

    def test_valid_grant_is_accepted_and_wrong_transfer_transaction_is_denied(self):
        client = WitnessQuorumClient(["http://a"], "show", "node", b"key")
        raw = {"granted": True, "clusterId": "show", "holderNodeId": "node", "epoch": 1, "expiresAtUnixMs": 9999999999999}
        self.assertTrue(client._parse_result("http://a", raw, "node").granted)
        response = MagicMock()
        def reply(request, **kwargs):
            payload = json.loads(request.data)
            response.__enter__.return_value.read.return_value = json.dumps(sign_response({**raw, "holderNodeId": "new", "transactionId": 8}, payload, "transfer", b"key")).encode()
            return response
        with patch("witness.urlopen", side_effect=reply):
            result = client._transfer_one("http://a", {"targetNodeId": "new", "transactionId": 9})
        self.assertFalse(result.granted)
        self.assertIn("transaction", result.error)

    def test_transfer_grants_expired_during_collection_do_not_form_quorum(self):
        client = WitnessQuorumClient(["http://a"], "show", "node", b"key")
        with patch.object(client, "_transfer_one", return_value=WitnessResult("http://a", True, 2, 1, "new")):
            result = client.transfer(target_node_id="new", source_epoch=1, target_epoch=2, transaction_id=9)
        self.assertFalse(result["transferred"])
        self.assertEqual(result["grants"], 0)
        self.assertTrue(client.status()["acquisitionSuspended"])

    def test_acquisition_checks_expiry_after_network_collection(self):
        client = WitnessQuorumClient(["http://a"], "show", "node", b"key")
        with patch("witness.time", return_value=1) as clock:
            def delayed_response(url):
                clock.return_value = 2
                return WitnessResult(url, True, 1, 1500, "node")
            with patch.object(client, "_one", side_effect=delayed_response):
                status = client.acquire()
            self.assertFalse(status["leaseValid"])
            self.assertEqual(status["leaseEpoch"], 0)
