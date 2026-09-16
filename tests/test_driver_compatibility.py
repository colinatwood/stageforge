import json
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
from driver_compatibility import assess_driver, load_catalog


class DriverCompatibilityTests(unittest.TestCase):
    def test_class_driver_evidence_is_specific(self):
        linux={"hardwareId":"USB:1234:ABCD","interfaceClasses":["01"],"driver":"snd-usb-audio","osProblem":None}
        self.assertEqual(assess_driver(linux,"Linux","6","x86_64")["status"],"class-driver-bound")
        linux["driver"]=""
        self.assertEqual(assess_driver(linux,"Linux","6","x86_64")["status"],"audio-class-detected-driver-unverified")
        self.assertEqual(assess_driver({"driver":"usbaudio2"},"Windows","11","AMD64")["status"],"class-driver-bound")

    @staticmethod
    def reviewed_package(**overrides):
        package={"hardwareId":"USB:1234:ABCD","product":"Reviewed Interface","os":"Windows","osReleases":["11"],"architecture":"AMD64",
                 "publisher":"Vendor","package":"Driver","version":"1.0","url":"https://vendor.example/driver","releaseDate":"2026-01-01",
                 "reviewedAt":"2026-09-01","reviewExpiresAt":"2027-03-01","reviewConfidence":"high","catalogClaim":"package-metadata-only",
                 "evidence":[{"kind":"vendor-download","url":"https://vendor.example/driver"},{"kind":"hardware-id-source","url":"https://ids.example/device"}]}
        package.update(overrides);return package

    def test_exact_catalog_match_requires_every_platform_dimension_and_current_review(self):
        package=self.reviewed_package();device={"hardwareId":"USB:1234:ABCD","driver":None,"osProblem":None}
        match=assess_driver(device,"Windows","11","AMD64",[package],as_of=date(2026,9,13))
        self.assertEqual(match["status"],"curated-exact-match");self.assertFalse(match["automaticInstallAllowed"])
        self.assertFalse(match["catalogReviewRequired"]);self.assertEqual(match["exactPackages"][0]["reviewState"],"current")
        self.assertEqual(assess_driver(device,"Windows","10","AMD64",[package],as_of=date(2026,9,13))["status"],"no-verified-match")
        self.assertEqual(assess_driver(device,"Windows","11","ARM64",[package],as_of=date(2026,9,13))["status"],"no-verified-match")

    def test_stale_and_legacy_entries_never_become_current_curated_matches(self):
        device={"hardwareId":"USB:1234:ABCD","driver":None,"osProblem":None}
        stale=self.reviewed_package(reviewExpiresAt="2026-09-12")
        report=assess_driver(device,"Windows","11","AMD64",[stale],as_of=date(2026,9,13))
        self.assertEqual(report["status"],"curated-match-review-stale");self.assertTrue(report["catalogReviewRequired"]);self.assertTrue(report["catalogReviewStale"])
        legacy={key:value for key,value in stale.items() if key not in ("product","releaseDate","reviewedAt","reviewExpiresAt","reviewConfidence","catalogClaim","evidence")}
        report=assess_driver(device,"Windows","11","AMD64",[legacy],as_of=date(2026,9,13))
        self.assertEqual(report["status"],"curated-match-unreviewed");self.assertTrue(report["catalogReviewRequired"])

    def test_catalog_rejects_partial_and_insecure_entries_but_reads_v1_compatibility(self):
        valid=self.reviewed_package(os="Linux",osReleases=["6"],architecture="x86_64")
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/"catalog.json"
            path.write_text(json.dumps({"schemaVersion":2,"packages":[valid,{**valid,"url":"http://bad.example"},{**valid,"hardwareId":"USB:any"}]}))
            self.assertEqual(load_catalog(path),[valid])
            legacy={key:value for key,value in valid.items() if key not in ("product","releaseDate","reviewedAt","reviewExpiresAt","reviewConfidence","catalogClaim","evidence")}
            path.write_text(json.dumps({"schemaVersion":1,"packages":[legacy]}));self.assertEqual(load_catalog(path),[legacy])

    def test_bundled_catalog_has_reviewed_multi_source_entries_and_no_qualification_claim(self):
        catalog=load_catalog(Path(__file__).resolve().parents[1]/"packaging/driver-catalog.json")
        self.assertGreaterEqual(len(catalog),2)
        for item in catalog:
            self.assertEqual(item["catalogClaim"],"package-metadata-only")
            self.assertGreaterEqual(len(item["evidence"]),2)
            report=assess_driver({"hardwareId":item["hardwareId"]},item["os"],item["osReleases"][-1],item["architecture"],catalog,as_of=date(2026,9,14))
            self.assertEqual(report["status"],"curated-exact-match")
            self.assertEqual(report["qualification"],"hardware-tests-required")
            self.assertFalse(report["automaticInstallAllowed"])

    def test_bundled_focusrite_4th_gen_records_are_current_windows_x64_metadata_only(self):
        catalog=load_catalog(Path(__file__).resolve().parents[1]/"packaging/driver-catalog.json")
        expected={"USB:1235:8218","USB:1235:8219","USB:1235:821A"}
        found={item["hardwareId"]:item for item in catalog if item.get("publisher")=="Focusrite" and item.get("hardwareId") in expected}
        self.assertEqual(set(found),expected)
        for hardware_id,item in found.items():
            self.assertEqual(item["architecture"],"AMD64");self.assertEqual(item["osReleases"],["10","11"]);self.assertIn("4.150.0.432",item["version"])
            report=assess_driver({"hardwareId":hardware_id},"Windows","11","AMD64",catalog,as_of=date(2026,9,14))
            self.assertEqual(report["status"],"curated-exact-match");self.assertEqual(report["qualification"],"hardware-tests-required");self.assertFalse(report["automaticInstallAllowed"])
            self.assertEqual(assess_driver({"hardwareId":hardware_id},"Windows","11","ARM64",catalog,as_of=date(2026,9,14))["status"],"no-verified-match")

    def test_os_problem_overrides_package_match(self):
        device={"hardwareId":"USB:1234:ABCD","osProblem":28}
        self.assertEqual(assess_driver(device,"Windows","11","AMD64",[])["status"],"os-problem")
