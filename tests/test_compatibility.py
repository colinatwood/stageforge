import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from compatibility import compatibility_report, inspect_show_state, migrate_show_state, resolve_requirements
from state import ShowState


class CompatibilityTests(unittest.TestCase):
    def test_future_readable_show_state_preserves_unknown_fields(self):
        base = ShowState().persistence_snapshot()
        future = copy.deepcopy(base)
        future["apiVersion"] = 2
        future["compatibility"] = {
            "documentType": "org.upp.show-state",
            "schemaVersion": 2,
            "minimumReaderApiVersion": 1,
            "unknownFieldsPreserved": True,
            "futureGovernanceHint": {"mode": "strange"},
        }
        future["futureTopLevel"] = {"answer": 42}
        future["transport"]["futureBeatGeometry"] = {"swingSpace": "non-euclidean"}
        future["audio"]["futureSpatialBus"] = {"dimensions": 7}

        state = ShowState(future)
        out = state.persistence_snapshot()
        self.assertEqual(out["apiVersion"], 2)
        self.assertEqual(out["futureTopLevel"], {"answer": 42})
        self.assertEqual(out["transport"]["futureBeatGeometry"]["swingSpace"], "non-euclidean")
        self.assertEqual(out["audio"]["futureSpatialBus"]["dimensions"], 7)
        self.assertEqual(out["compatibility"]["futureGovernanceHint"]["mode"], "strange")
        self.assertEqual(state.compatibility_status()["mode"], "forward-compatible")

    def test_future_show_state_can_require_newer_reader(self):
        snapshot = {
            "apiVersion": 3,
            "compatibility": {
                "documentType": "org.upp.show-state",
                "minimumReaderApiVersion": 2,
            },
        }
        report = inspect_show_state(snapshot)
        self.assertFalse(report["readable"])
        self.assertEqual(report["mode"], "reader-too-old")
        with self.assertRaises(ValueError):
            ShowState(snapshot)

    def test_legacy_v0_migration_is_explicit_and_lossless(self):
        legacy = ShowState().persistence_snapshot()
        legacy.pop("apiVersion", None)
        legacy.pop("compatibility", None)
        legacy["transport"]["tempo"] = 133
        legacy["transport"].pop("bpm", None)
        legacy["transport"]["positionSeconds"] = 12.5
        legacy["transport"].pop("seconds", None)
        legacy["system"]["resourceCapacity"] = 66
        legacy["system"].pop("capacity", None)
        legacy["audio"]["outputDeviceId"] = "legacy-device"
        legacy["audio"].pop("deviceId", None)
        legacy["oldVendorBlob"] = {"preserveMe": True}

        normalized, report = migrate_show_state(legacy)
        self.assertEqual(normalized["apiVersion"], 1)
        self.assertIn("transport.tempo->transport.bpm", report["migrations"])
        state = ShowState(legacy)
        out = state.persistence_snapshot()
        self.assertEqual(out["transport"]["bpm"], 133)
        self.assertEqual(out["transport"]["seconds"], 12.5)
        self.assertEqual(out["system"]["capacity"], 66)
        self.assertEqual(out["audio"]["deviceId"], "legacy-device")
        self.assertTrue(out["oldVendorBlob"]["preserveMe"])

    def test_compatibility_negotiation_uses_only_explicit_adapters(self):
        local = {
            "id": "old-console",
            "apiVersions": [1],
            "capabilities": ["upp.audio.output/1", "legacy.lighting/1"],
            "requiredCapabilities": ["upp.audio.output/1"],
            "adapters": [{"from": "legacy.lighting/1", "to": "upp.lighting.output/2", "quality": "acceptable"}],
        }
        remote = {
            "id": "new-console",
            "apiVersions": [1, 2],
            "capabilities": ["upp.audio.output/1", "upp.lighting.output/2", "future.hologram/9"],
            "requiredCapabilities": ["upp.lighting.output/2"],
        }
        report = compatibility_report(local, remote)
        self.assertTrue(report["compatible"])
        self.assertEqual(report["selectedApiVersion"], 1)
        self.assertEqual(report["directCapabilities"], ["upp.audio.output/1"])
        self.assertEqual(len(report["translations"]), 1)
        self.assertIn("future.hologram/9", report["remoteOnlyPreserved"])
        self.assertEqual(report["grade"], "acceptable")

        no_adapter = copy.deepcopy(local)
        no_adapter["adapters"] = []
        blocked = compatibility_report(no_adapter, remote)
        self.assertFalse(blocked["compatible"])
        self.assertTrue(any("required capabilities" in item for item in blocked["blockers"]))

    def test_show_requirement_resolution_reports_explicit_fallback_quality(self):
        participant = {
            "apiVersions": [1],
            "capabilities": ["audio.transport", "authority.fence", "audio.mix", "lighting.state"],
            "preservesUnknown": True,
        }
        result = resolve_requirements(participant, [
            {"id": "transport", "preferred": "audio.transport", "required": True},
            {"id": "output", "preferred": "audio.output.multi", "required": True, "alternatives": [{"capability": "audio.mix", "quality": "acceptable"}]},
            {"id": "lighting", "preferred": "lighting.artnet.send", "required": True, "alternatives": [{"capability": "lighting.state", "quality": "degraded"}]},
        ])
        self.assertTrue(result["compatible"])
        self.assertEqual(result["grade"], "degraded")
        by_id = {item["id"]: item for item in result["requirements"]}
        self.assertEqual(by_id["output"]["status"], "fallback")
        self.assertEqual(by_id["output"]["qualityScore"], 80)
        self.assertEqual(by_id["lighting"]["qualityScore"], 60)

    def test_no_common_api_blocks_even_when_capabilities_match(self):
        report = compatibility_report(
            {"apiVersions": [1], "capabilities": ["x"]},
            {"apiVersions": [2], "capabilities": ["x"]},
        )
        self.assertFalse(report["compatible"])
        self.assertIn("no common API version", report["blockers"])


if __name__ == "__main__":
    unittest.main()
