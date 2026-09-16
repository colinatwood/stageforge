import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from dev_server import RequestRateLimiter
from http_workload import percentile, simulate_rate_policy, summarize_http_results


class HttpWorkloadQualificationTests(unittest.TestCase):
    def test_percentile_is_nearest_rank_and_bounded(self):
        self.assertEqual(percentile([4, 1, 3, 2], .5), 2)
        self.assertEqual(percentile([4, 1, 3, 2], .95), 4)
        self.assertEqual(percentile([], .95), 0)

    def test_default_rate_policy_preserves_representative_controller_load(self):
        result = simulate_rate_policy(lambda clock: RequestRateLimiter(clock=clock))
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["controllersDenied"], 0)
        self.assertGreater(result["attackerDenied"], 0)

    def test_http_summary_requires_expected_status_and_latency_envelope(self):
        results = [{"status": 200, "latencyMs": value} for value in (1, 2, 3, 4, 5)]
        self.assertTrue(summarize_http_results(results, {200}, max_p95_ms=5)["passed"])
        self.assertFalse(summarize_http_results(results, {200}, max_p95_ms=4)["passed"])
        self.assertFalse(summarize_http_results(results + [{"status": 503, "latencyMs": 1}], {200})["passed"])


if __name__ == "__main__":
    unittest.main()
