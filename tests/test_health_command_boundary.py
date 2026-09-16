import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from dev_server import StageForgeHandler, validate_http_boundary


class HealthCommandBoundaryTests(unittest.TestCase):
    def test_remote_health_requires_api_token(self):
        env = {'STAGEFORGE_API_TOKEN': 'secret'}
        with self.assertRaises(PermissionError):
            validate_http_boundary({'Host': 'localhost'}, '192.0.2.1', '/healthz', 'GET', env)
        validate_http_boundary({'Host': 'localhost', 'X-StageForge-API-Token': 'secret'},
                               '192.0.2.1', '/healthz', 'GET', env)

    def test_proxy_health_requires_api_token(self):
        with self.assertRaises(PermissionError):
            validate_http_boundary({'Host': 'localhost'}, '127.0.0.1', '/healthz', 'GET',
                                   {'STAGEFORGE_REQUIRE_API_TOKEN': '1', 'STAGEFORGE_API_TOKEN': 'secret'})

    def test_local_health_stays_available_in_development(self):
        validate_http_boundary({'Host': 'localhost'}, '127.0.0.1', '/healthz', 'GET', {})

    def test_command_ids_are_not_silently_aliased(self):
        handler = object.__new__(StageForgeHandler)
        prefix = 'a' * 128
        handler.headers = {'X-StageForge-Command-Id': prefix}
        self.assertEqual(handler._command_id(), prefix)
        for suffix in ('x', 'y'):
            handler.headers = {'X-StageForge-Command-Id': prefix + suffix}
            with self.assertRaises(ValueError):
                handler._command_id()
        handler.headers = {'X-StageForge-Command-Id': '  '}
        self.assertIsNone(handler._command_id())
