import json
import http.client
import threading
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from http_credentials import credential_environment
from dev_server import StageForgeHandler, StageForgeHTTPServer, validate_http_boundary


class CredentialTests(unittest.TestCase):
    def test_keepalive_request_reads_replacement_credentials(self):
        self.write({'STAGEFORGE_API_TOKEN': 'a' * 32})
        server = StageForgeHTTPServer(('127.0.0.1', 0), StageForgeHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        conn = http.client.HTTPConnection(*server.server_address, timeout=2)
        try:
            with patch.dict('os.environ', self.env, clear=True), patch('dev_server.RUNTIME.health', return_value={'ok': True}):
                conn.request('GET', '/healthz', headers={'X-StageForge-API-Token': 'a' * 32})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                self.write({'STAGEFORGE_API_TOKEN': 'b' * 32})
                conn.request('GET', '/healthz', headers={'X-StageForge-API-Token': 'b' * 32})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                conn.request('GET', '/healthz', headers={'X-StageForge-API-Token': 'a' * 32})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
        finally:
            conn.close()
            server.shutdown()
            server.server_close()
            worker.join(2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'credentials.json'
        self.env = {'STAGEFORGE_HTTP_CREDENTIAL_FILE': str(self.path),
                    'STAGEFORGE_ADMIN_API_TOKEN': 'legacy-admin'}

    def write(self, tokens):
        replacement = self.path.with_suffix('.new')
        replacement.write_text(json.dumps(tokens))
        replacement.chmod(0o600)
        replacement.replace(self.path)

    def test_file_replaces_all_http_tokens_and_forces_auth(self):
        self.write({'STAGEFORGE_API_TOKEN': 'a' * 32})
        env = credential_environment(self.env)
        self.assertEqual(env['STAGEFORGE_REQUIRE_API_TOKEN'], '1')
        self.assertNotIn('STAGEFORGE_ADMIN_API_TOKEN', env)
        with self.assertRaises(PermissionError):
            validate_http_boundary({'Host': 'localhost'}, '127.0.0.1', '/healthz', 'GET', env)

    def test_replacement_rotates_next_snapshot_without_mutating_inflight(self):
        self.write({'STAGEFORGE_API_TOKEN': 'a' * 32})
        with patch.dict('os.environ', self.env, clear=True):
            first = object.__new__(StageForgeHandler)
            first._credentials()
            self.write({'STAGEFORGE_API_TOKEN': 'b' * 32})
            second = object.__new__(StageForgeHandler)
            self.assertEqual(first._credentials()['STAGEFORGE_API_TOKEN'], 'a' * 32)
            env = second._credentials()
            self.assertEqual(env['STAGEFORGE_API_TOKEN'], 'b' * 32)
            with self.assertRaises(PermissionError):
                validate_http_boundary({'Host': 'localhost', 'X-StageForge-API-Token': 'a' * 32},
                                       '127.0.0.1', '/healthz', 'GET', env)

    def test_invalid_replacement_never_uses_old_or_environment_secret(self):
        self.write({'STAGEFORGE_API_TOKEN': 'a' * 32})
        credential_environment(self.env)
        self.path.write_text('not json')
        with self.assertRaises(PermissionError):
            credential_environment({**self.env, 'STAGEFORGE_API_TOKEN': 'fallback'})

    def test_unsafe_permissions_and_symlinks_fail_closed(self):
        self.write({'STAGEFORGE_API_TOKEN': 'a' * 32})
        self.path.chmod(0o644)
        with self.assertRaises(PermissionError):
            credential_environment(self.env)
        self.path.chmod(0o600)
        link = self.path.with_suffix('.link')
        link.symlink_to(self.path)
        with self.assertRaises(PermissionError):
            credential_environment({'STAGEFORGE_HTTP_CREDENTIAL_FILE': str(link)})

    def test_schema_size_and_role_overlap_are_rejected(self):
        for tokens in ({}, {'unknown': 'a' * 32}, {'STAGEFORGE_API_TOKEN': 'short'},
                       {'STAGEFORGE_API_TOKEN': 'a' * 32, 'STAGEFORGE_MONITOR_API_TOKEN': 'a' * 32}):
            self.write(tokens)
            with self.assertRaises(PermissionError):
                credential_environment(self.env)
        self.path.write_text(' ' * 16385)
        with self.assertRaises(PermissionError):
            credential_environment(self.env)

    def test_duplicate_json_keys_are_rejected(self):
        self.write({'STAGEFORGE_API_TOKEN': 'a' * 32})
        self.path.write_text('{"STAGEFORGE_API_TOKEN":"' + 'a' * 32 + '","STAGEFORGE_API_TOKEN":"' + 'b' * 32 + '"}')
        with self.assertRaises(PermissionError):
            credential_environment(self.env)
