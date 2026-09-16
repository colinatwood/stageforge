import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from interoperability_sessions import CapabilityRegistry, InteroperabilitySessionManager, make_authenticated_offer, project_profile, verify_authenticated_offer
from hardware_bench import analyze_hardware_samples


class InteroperabilitySessionTests(unittest.TestCase):
    def participants(self):
        local={"id":"local","apiVersions":[1,2],"schemaVersions":{"org.upp.show-state":[1]},"capabilities":["audio.transport"],"requiredCapabilities":["audio.transport"],"preservesUnknown":True,"offlineCapable":True}
        remote={**local,"id":"remote","capabilities":["audio.transport","vendor.future"]}
        return local,remote

    def test_authenticated_lifecycle_replay_and_change_invalidation(self):
        local,remote=self.participants();secret=b"shared-test-key";now=1_000_000
        offer=make_authenticated_offer(remote,"local",authority_epoch=7,sequence=1,ttl_ms=1000,secret=secret,now_unix_ms=now,nonce="00112233445566778899aabbccddeeff")
        manager=InteroperabilitySessionManager("local");registry=CapabilityRegistry()
        session=manager.authenticate_and_negotiate(offer,local,registry,secret=secret,now_unix_ms=now,profile_revision=3,authority_epoch=7)
        self.assertEqual(session["state"],"negotiated");self.assertTrue(session["plan"]["unknownPreservation"])
        projection=project_profile({"profileId":"p","revision":3,"preferences":[]})
        self.assertEqual(manager.consent(session["sessionId"],projection,accepted=True)["state"],"consented")
        active=manager.activate(session["sessionId"],now_unix_ms=now,profile_revision=3,registry_revision=0,authority_epoch=7)
        self.assertEqual(active["state"],"active");self.assertFalse(active["physicalOutputsArmed"])
        with self.assertRaises(ValueError):manager.authenticate_and_negotiate(offer,local,registry,secret=secret,now_unix_ms=now,profile_revision=3,authority_epoch=7)

    def test_transcript_tamper_and_downgrade_fail(self):
        local,remote=self.participants();secret=b"shared-test-key";now=1_000_000
        offer=make_authenticated_offer(remote,"local",authority_epoch=7,sequence=1,ttl_ms=1000,secret=secret,now_unix_ms=now)
        offer["participant"]["capabilities"].append("tampered")
        self.assertFalse(verify_authenticated_offer(offer,expected_target="local",secret=secret,now_unix_ms=now)[0])
        remote["apiVersions"]=[1];remote["minimumSecureApiVersion"]=2
        offer=make_authenticated_offer(remote,"local",authority_epoch=7,sequence=2,ttl_ms=1000,secret=secret,now_unix_ms=now)
        with self.assertRaisesRegex(ValueError,"downgrade"):
            InteroperabilitySessionManager("local").authenticate_and_negotiate(offer,local,CapabilityRegistry(),secret=secret,now_unix_ms=now,profile_revision=1,authority_epoch=7)

    def test_profile_projection_consent_and_accessibility_priority(self):
        profile={"profileId":"p","revision":1,"preferences":[
            {"namespace":"org.upp.accessibility.visual","key":"contrast","layer":"user","revision":1,"type":"scalar","value":0.9},
            {"namespace":"org.upp.accessibility.visual","key":"contrast","layer":"venue","revision":2,"type":"scalar","value":0.3},
            {"namespace":"org.upp.ui","key":"density","layer":"user","revision":1,"type":"token","value":"comfortable"},
            {"namespace":"org.upp.ui","key":"density","layer":"venue","revision":2,"type":"token","value":"compact"}]}
        projection=project_profile(profile);values={(x["namespace"],x["key"]):x["value"] for x in projection["values"]}
        self.assertEqual(values[("org.upp.accessibility.visual","contrast")],0.9)
        self.assertEqual(values[("org.upp.ui","density")],"compact");self.assertEqual(len(projection["consentRequired"]),1)

    def test_hardware_bench_never_labels_loopback_as_measured(self):
        samples=[{"sequence":1,"transportLatencyNs":2_000_000,"jitterNs":10_000,"clockOffsetNs":500},
                 {"sequence":3,"transportLatencyNs":2_200_000,"jitterNs":20_000,"clockOffsetNs":700}]
        report=analyze_hardware_samples(samples,source="loopback",duration_ms=1000)
        self.assertFalse(report["measured"]);self.assertEqual(report["qualification"],"simulation-only");self.assertEqual(report["lostSequences"],1);self.assertFalse(report["physicalOutputsArmed"])
        with self.assertRaises(ValueError):analyze_hardware_samples(samples,source="hardware",duration_ms=1000)

if __name__=="__main__":unittest.main()
