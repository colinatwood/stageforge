import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from witness import WitnessQuorumClient, sign_response, verify_response


class WitnessResponseAuthTests(unittest.TestCase):
    def setUp(self):
        self.request = {"protocolVersion":1, "clusterId":"show", "nodeId":"node", "ttlMs":3000, "nonce":"fresh"}
        self.grant = {"granted":True, "clusterId":"show", "holderNodeId":"node", "epoch":1, "expiresAtUnixMs":9999999999999}
        self.key = b"test-key"

    def test_authenticated_grant_and_denial(self):
        for granted in (True, False):
            result = {**self.grant, "granted":granted}
            signed = sign_response(result, self.request, "acquire", self.key)
            self.assertEqual(verify_response(signed, self.request, "acquire", self.key)["granted"], granted)

    def test_tampering_wrong_key_and_unsigned_reply_fail(self):
        signed = sign_response(self.grant, self.request, "acquire", self.key)
        for raw, key in ((self.grant,self.key), ({**signed,"epoch":2},self.key),
                         ({**signed,"expiresAtUnixMs":99999999999999},self.key), (signed,b"wrong")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                verify_response(raw, self.request, "acquire", key)

    def test_replay_and_operation_reflection_fail(self):
        signed = sign_response(self.grant, self.request, "acquire", self.key)
        for request, operation in (({**self.request,"nonce":"next"}, "acquire"),
                                   ({**self.request,"ttlMs":500}, "acquire"), (self.request,"transfer")):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, "binding"):
                verify_response(signed, request, operation, self.key)

    def test_network_client_requires_current_request_signature(self):
        client = WitnessQuorumClient(["http://witness"], "show", "node", self.key)
        previous = None
        def reply(request, **kwargs):
            nonlocal previous
            payload = json.loads(request.data)
            response = MagicMock()
            signed = sign_response(self.grant, payload, "acquire", self.key)
            response.__enter__.return_value.read.return_value = json.dumps(previous or signed).encode()
            previous = signed
            return response
        with patch("witness.urlopen", side_effect=reply):
            self.assertTrue(client._one("http://witness").granted)
            self.assertFalse(client._one("http://witness").granted)

    def test_production_handler_signs_acquisition_and_transfer(self):
        from http.server import ThreadingHTTPServer
        from threading import Thread
        import witness_server
        from witness import WitnessLeaseStore
        with patch.object(witness_server, "SECRET", self.key), patch.object(witness_server, "STORE", WitnessLeaseStore()):
            server = ThreadingHTTPServer(("127.0.0.1",0), witness_server.Handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = WitnessQuorumClient([f"http://127.0.0.1:{server.server_port}"], "show", "node", self.key)
                acquired = client.acquire()
                self.assertTrue(acquired["leaseValid"])
                epoch = acquired["leaseEpoch"]
                moved = client.transfer(target_node_id="target", source_epoch=epoch, target_epoch=epoch+1, transaction_id=42)
                self.assertTrue(moved["transferred"])
                self.assertTrue(client.status()["acquisitionSuspended"])
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()
