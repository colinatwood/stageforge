import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from user_profiles import UserProfileStore, inspect_user_profile, normalize_user_profile, resolve_user_preferences


class UserProfileTests(unittest.TestCase):
    def profile(self):
        return {
            "documentType": "org.upp.user-profile", "schemaVersion": 1,
            "minimumReaderSchemaVersion": 1, "profileId": "performer-alex", "revision": 1,
            "futureIdentityHint": {"preserve": True},
            "preferences": [
                {"namespace": "org.upp.ui", "key": "contrast", "layer": "base", "revision": 1, "type": "scalar", "value": 0.5},
                {"namespace": "org.upp.ui", "key": "contrast", "layer": "user", "revision": 2, "type": "scalar", "value": 0.8},
                {"namespace": "org.upp.ui", "key": "contrast", "layer": "session", "revision": 3, "type": "scalar", "value": 1.0},
            ],
        }

    def test_layer_resolution_and_unknown_preservation(self):
        profile = normalize_user_profile(self.profile())
        self.assertTrue(profile["futureIdentityHint"]["preserve"])
        self.assertTrue(profile["unknownFieldsPreserved"])
        resolved = resolve_user_preferences(profile)
        self.assertEqual(resolved["resolved"][0]["layer"], "session")
        self.assertEqual(resolved["resolved"][0]["value"], 1.0)
        self.assertFalse(resolved["physicalOutputsArmed"])

    def test_newer_required_reader_fails_closed(self):
        profile = self.profile(); profile["schemaVersion"] = 3; profile["minimumReaderSchemaVersion"] = 2
        self.assertFalse(inspect_user_profile(profile)["readable"])
        with self.assertRaises(ValueError): normalize_user_profile(profile)

    def test_store_requires_advancing_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            store = UserProfileStore(Path(directory) / "profile.json")
            saved = store.save(self.profile())
            self.assertEqual(saved["profileId"], "performer-alex")
            with self.assertRaises(ValueError): store.save(self.profile())
            updated = self.profile(); updated["revision"] = 2
            self.assertEqual(store.save(updated)["revision"], 2)


if __name__ == "__main__": unittest.main()
