import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from state import RevisionConflict, ShowState


class ShowStateTests(unittest.TestCase):
    def setUp(self):
        self.state = ShowState()

    def test_monitor_is_player_scoped(self):
        before = self.state.snapshot()
        sam_before = next(p for p in before["players"] if p["id"] == "sam")["monitor"]["self"]
        self.state.patch_monitor("alex", {"self": 99})
        after = self.state.snapshot()
        alex = next(p for p in after["players"] if p["id"] == "alex")
        sam = next(p for p in after["players"] if p["id"] == "sam")
        self.assertEqual(alex["monitor"]["self"], 99)
        self.assertEqual(sam["monitor"]["self"], sam_before)

    def test_capacity_is_clamped(self):
        state = self.state.patch_system({"capacity": 500})
        self.assertEqual(state["system"]["capacity"], 100)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            self.state.patch_system({"mode": "explode"})

    def test_transport_stop_resets_time(self):
        self.state.transport("play")
        state = self.state.transport("stop")
        self.assertFalse(state["transport"]["running"])
        self.assertEqual(state["transport"]["seconds"], 0)


    def test_resource_revision_is_scoped(self):
        state = ShowState()
        first = state.snapshot()
        monitor_rev = first["resourceRevisions"]["monitor:alex"]
        system_rev = first["resourceRevisions"]["system"]
        state.patch_system({"capacity": 55}, first["revision"], system_rev)
        # Alex monitor token remains valid despite unrelated global revision change.
        changed = state.patch_monitor("alex", {"self": 80}, first["revision"], monitor_rev)
        self.assertEqual(changed["players"][0]["monitor"]["self"], 80)
        with self.assertRaises(RevisionConflict):
            state.patch_monitor("alex", {"self": 81}, None, monitor_rev)

    def test_revision_conflict_rejected(self):
        revision = self.state.revision
        self.state.patch_show({"bpm": 121}, expected_revision=revision)
        with self.assertRaises(RevisionConflict):
            self.state.patch_show({"bpm": 122}, expected_revision=revision)

    def test_event_ids_increase(self):
        first = self.state.latest_event()["eventId"]
        self.state.patch_show({"key": "D"})
        second = self.state.latest_event()["eventId"]
        self.assertGreater(second, first)
        events = self.state.events_since(first)
        self.assertEqual([event["eventId"] for event in events], [second])

    def test_restore_preserves_completed_notation_capture(self):
        self.state.notation_note("sam", {"action": "on", "pitch": 43, "velocity": 90, "showTimeSeconds": 1.0})
        self.state.notation_note("sam", {"action": "off", "pitch": 43, "showTimeSeconds": 1.5})
        restored = ShowState(self.state.persistence_snapshot())
        notes = restored.snapshot()["notation"]["sam"]["notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["pitch"], 43)

    def test_midi_binding_and_activity_are_persisted(self):
        first = self.state.snapshot()
        self.state.bind_midi_device("controller-a", "alex", first["revision"], first["resourceRevisions"]["midi-bindings"])
        self.state.ingest_midi("alex", {"deviceId": "controller-a", "status": 0xB0, "data1": 1, "data2": 64, "showTimeSeconds": 1.0})
        snapshot = self.state.persistence_snapshot()
        restored = ShowState(snapshot)
        midi = restored.snapshot()["midi"]
        self.assertEqual(midi["bindings"]["controller-a"], "alex")
        self.assertEqual(midi["received"], 1)
        self.assertEqual(midi["activity"][-1]["data1"], 1)

    def test_midi_activity_revision_is_separate_from_notation(self):
        first = self.state.snapshot()
        midi_rev = first["resourceRevisions"]["midi:alex"]
        notation_rev = first["resourceRevisions"]["notation:alex"]
        result = self.state.ingest_midi("alex", {"status": 0xB0, "data1": 7, "data2": 100}, None, midi_rev)
        self.assertGreater(result["resourceRevisions"]["midi:alex"], midi_rev)
        self.assertEqual(result["resourceRevisions"]["notation:alex"], notation_rev)
        self.assertEqual(result["midi"]["received"], 1)

    def test_restore_holds_transport_paused(self):
        self.state.transport("play")
        snapshot = self.state.snapshot()
        restored = ShowState(snapshot)
        restored_snapshot = restored.snapshot()
        self.assertFalse(restored_snapshot["transport"]["running"])
        self.assertGreaterEqual(restored_snapshot["transport"]["seconds"], 0)
        self.assertEqual(restored_snapshot["transport"]["bpm"], snapshot["transport"]["bpm"])


    def test_lighting_network_desired_state_is_scoped_and_persisted(self):
        state = ShowState()
        revision = state.snapshot()["resourceRevisions"]["lighting-network"]
        updated = state.patch_lighting_network(
            {"protocol": "sacn", "target": "127.0.0.1", "port": 5568, "universeBase": 101},
            expected_resource_revision=revision,
        )
        self.assertEqual(updated["lighting"]["network"]["target"], "127.0.0.1")
        self.assertEqual(updated["lighting"]["network"]["protocol"], "sacn")
        self.assertEqual(updated["lighting"]["network"]["universeBase"], 101)
        self.assertFalse(updated["lighting"]["network"]["armed"])
        restored = ShowState(state.persistence_snapshot()).snapshot()
        self.assertEqual(restored["lighting"]["network"]["target"], "127.0.0.1")
        self.assertEqual(restored["lighting"]["network"]["protocol"], "sacn")
        self.assertEqual(restored["lighting"]["network"]["universeBase"], 101)
        self.assertFalse(restored["lighting"]["network"]["armed"])

    def test_audio_state_is_scoped_and_persisted(self):
        state = ShowState()
        before = state.snapshot()
        audio_revision = before["resourceRevisions"]["audio"]
        changed = state.patch_audio(
            {"deviceId": "venue-interface", "sampleRate": 96000, "bufferFrames": 128, "limiterCeilingDb": -2.5},
            expected_resource_revision=audio_revision,
        )
        self.assertEqual(changed["audio"]["deviceId"], "venue-interface")
        self.assertEqual(changed["audio"]["sampleRate"], 96000)
        self.assertEqual(changed["audio"]["bufferFrames"], 128)
        self.assertEqual(changed["audio"]["limiterCeilingDb"], -2.5)
        self.assertEqual(changed["resourceRevisions"]["monitor:alex"], before["resourceRevisions"]["monitor:alex"])
        restored = ShowState(state.persistence_snapshot()).snapshot()
        self.assertEqual(restored["audio"]["deviceId"], "venue-interface")
        self.assertEqual(restored["audio"]["sampleRate"], 96000)


    def test_audio_input_player_restores_after_dynamic_player_roster(self):
        snapshot = self.state.persistence_snapshot()
        snapshot["players"] = [{
            "id": "guest-keys",
            "name": "Guest Keys",
            "role": "Keys",
            "mode": "local",
            "available": True,
            "monitor": {
                "master": 72, "self": 76, "vocals": 58, "band": 62,
                "click": 38, "talkback": 45, "ambient": 28,
                "muted": False, "output": "IEM A"
            },
        }]
        snapshot["audio"]["inputPlayerId"] = "guest-keys"
        restored = ShowState(snapshot).snapshot()
        self.assertEqual(restored["players"][0]["id"], "guest-keys")
        self.assertEqual(restored["audio"]["inputPlayerId"], "guest-keys")

    def test_multiple_audio_inputs_are_independent_and_legacy_slot_zero_survives(self):
        state = ShowState()
        revision = state.snapshot()["resourceRevisions"]["audio"]
        updated = state.patch_audio({
            "inputs": [
                {"slot": 0, "deviceId": "capture-a", "playerId": "alex", "sampleRate": 44100, "route": {"output": 0, "gain": 0.2}},
                {"slot": 1, "deviceId": "capture-b", "playerId": "jordan", "sampleRate": 96000, "route": {"output": 3, "gain": 0.7}},
            ]
        }, expected_resource_revision=revision)
        self.assertEqual(updated["audio"]["inputs"][1]["playerId"], "jordan")
        self.assertEqual(updated["audio"]["inputs"][1]["route"]["output"], 3)
        self.assertEqual(updated["audio"]["inputs"][0]["sampleRate"], 44100)
        self.assertEqual(updated["audio"]["inputs"][1]["sampleRate"], 96000)
        self.assertEqual(updated["audio"]["engineSampleRate"], 192000)
        self.assertEqual(updated["audio"]["engineSampleFormat"], "float32")
        self.assertEqual(updated["audio"]["inputDeviceId"], "capture-a")
        restored = ShowState(state.persistence_snapshot()).snapshot()
        self.assertEqual(restored["audio"]["inputs"][0]["playerId"], "alex")
        self.assertEqual(restored["audio"]["inputs"][1]["deviceId"], "capture-b")
        self.assertEqual(restored["audio"]["inputs"][0]["sampleRate"], 44100)

        legacy = ShowState()
        legacy.patch_audio({"sampleRate": 48000})
        self.assertTrue(all(item["sampleRate"] == 48000 for item in legacy.snapshot()["audio"]["inputs"]))

    def test_audio_input_desired_state_and_route_persist(self):
        state = ShowState()
        revision = state.snapshot()["resourceRevisions"]["audio"]
        updated = state.patch_audio({
            "inputDeviceId": "alsa-capture-test",
            "inputPlayerId": "jordan",
            "inputRoute": {"output": 2, "gain": 0.5},
        }, expected_resource_revision=revision)
        self.assertEqual(updated["audio"]["inputDeviceId"], "alsa-capture-test")
        self.assertEqual(updated["audio"]["inputPlayerId"], "jordan")
        self.assertEqual(updated["audio"]["inputRoute"], {"output": 2, "gain": 0.5})
        restored = ShowState(state.persistence_snapshot()).snapshot()
        self.assertEqual(restored["audio"]["inputDeviceId"], "alsa-capture-test")
        self.assertEqual(restored["audio"]["inputRoute"]["output"], 2)
        self.assertEqual(restored["audio"]["inputRoute"]["gain"], 0.5)

    def test_multiple_audio_outputs_are_independent_and_legacy_slot_zero_survives(self):
        state = ShowState()
        updated = state.patch_audio({
            "outputs": [
                {"slot": 1, "deviceId": "iem-device", "purpose": "monitor", "playerId": "jordan", "graphOutput": 7, "master": 0.8, "limiterCeilingDb": -3.0},
                {"slot": 3, "deviceId": "broadcast-device", "purpose": "broadcast", "graphOutput": 12, "master": 0.9, "limiterCeilingDb": -2.0},
            ]
        })
        self.assertEqual(updated["audio"]["outputs"][1]["playerId"], "jordan")
        self.assertEqual(updated["audio"]["outputs"][3]["purpose"], "broadcast")
        self.assertEqual(updated["audio"]["deviceId"], "null-audio")
        state.patch_audio({"deviceId": "foh-device", "limiterCeilingDb": -4.0})
        snapshot = state.persistence_snapshot()
        self.assertEqual(snapshot["audio"]["outputs"][0]["deviceId"], "foh-device")
        self.assertEqual(snapshot["audio"]["outputs"][0]["limiterCeilingDb"], -4.0)
        restored = ShowState(snapshot).snapshot()
        self.assertEqual(restored["audio"]["outputs"][1]["deviceId"], "iem-device")
        self.assertEqual(restored["audio"]["outputs"][3]["graphOutput"], 12)

    def test_audio_output_drift_policy_is_scoped_and_persisted(self):
        state = ShowState()
        updated = state.patch_audio({
            "outputs": [{
                "slot": 2,
                "driftCompensation": {"enabled": False, "maxCorrectionPpm": 900.0, "queueGainPpm": 300.0},
            }]
        })
        policy = updated["audio"]["outputs"][2]["driftCompensation"]
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["maxCorrectionPpm"], 900.0)
        restored = ShowState(state.persistence_snapshot()).snapshot()
        self.assertEqual(restored["audio"]["outputs"][2]["driftCompensation"], policy)



if __name__ == "__main__":
    unittest.main()
