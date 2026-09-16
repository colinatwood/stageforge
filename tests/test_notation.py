import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from notation import NotationPart, midi_pitch_name, quantize_beats
from state import RevisionConflict, ShowState


class NotationTests(unittest.TestCase):
    def test_quantize_grid(self):
        self.assertEqual(quantize_beats(1.12, "1/16"), 1.0)
        self.assertEqual(quantize_beats(1.14, "1/8"), 1.0)
        self.assertEqual(quantize_beats(1.27, "1/8"), 1.5)
        self.assertEqual(quantize_beats(1.125, "1/16"), 1.25)

    def test_key_spelling_prefers_flats(self):
        self.assertEqual(midi_pitch_name(70, "Bb"), ("B", 4, -1))
        self.assertEqual(midi_pitch_name(70, "G"), ("A", 4, 1))

    def test_raw_performance_survives_requantization(self):
        part = NotationPart("alex")
        part.note_on(60, 100, 0.11, 120)
        part.note_off(60, 0.62, 120)
        first = part.snapshot("C")
        raw = first["rawNotes"][0].copy()
        part.settings.patch({"quantize": "1/8"})
        second = part.snapshot("C")
        self.assertEqual(second["rawNotes"][0], raw)
        self.assertNotEqual(first["notes"][0]["durationBeats"], 0)

    def test_show_state_notation_is_player_scoped_and_revisioned(self):
        state = ShowState()
        first = state.snapshot()
        alex_rev = first["resourceRevisions"]["notation:alex"]
        sam_rev = first["resourceRevisions"]["notation:sam"]
        state.notation_note("alex", {"action": "on", "pitch": 60, "velocity": 99, "showTimeSeconds": 0.1}, first["revision"], alex_rev)
        current = state.snapshot()
        alex_rev2 = current["resourceRevisions"]["notation:alex"]
        state.notation_note("alex", {"action": "off", "pitch": 60, "showTimeSeconds": 0.6}, current["revision"], alex_rev2)
        result = state.snapshot()
        self.assertEqual(len(result["notation"]["alex"]["notes"]), 1)
        self.assertEqual(len(result["notation"]["sam"]["notes"]), 0)
        self.assertEqual(result["resourceRevisions"]["notation:sam"], sam_rev)
        with self.assertRaises(RevisionConflict):
            state.patch_notation_settings("alex", {"quantize": "1/8"}, None, alex_rev)

    def test_live_snapshot_is_bounded_but_part_snapshot_retains_raw(self):
        state = ShowState()
        for i in range(20):
            start = i * 0.5
            state.notation_note("alex", {"action": "on", "pitch": 60 + (i % 3), "showTimeSeconds": start})
            state.notation_note("alex", {"action": "off", "pitch": 60 + (i % 3), "showTimeSeconds": start + 0.25})
        live = state.snapshot()["notation"]["alex"]
        full = state.notation_snapshot("alex")
        self.assertNotIn("rawNotes", live)
        self.assertEqual(len(live["notes"]), 16)
        self.assertEqual(live["rawNoteCount"], 20)
        self.assertEqual(len(full["rawNotes"]), 20)

    def test_midi_input_automatically_feeds_notation(self):
        state = ShowState()
        state.ingest_midi("jordan", {"status": 0x90, "data1": 62, "data2": 110, "showTimeSeconds": 2.0})
        state.ingest_midi("jordan", {"status": 0x80, "data1": 62, "data2": 0, "showTimeSeconds": 2.5})
        part = state.snapshot()["notation"]["jordan"]
        self.assertEqual(len(part["notes"]), 1)
        self.assertEqual(part["notes"][0]["pitch"], 62)
        self.assertTrue(state.latest_event()["payload"]["notationObserved"])

    def test_non_note_midi_does_not_touch_notation_revision(self):
        state = ShowState()
        before = state.snapshot()["resourceRevisions"]["notation:alex"]
        result = state.ingest_midi("alex", {"status": 0xB0, "data1": 1, "data2": 64, "showTimeSeconds": 1.0})
        self.assertEqual(result["resourceRevisions"]["notation:alex"], before)

    def test_musicxml_export(self):
        state = ShowState()
        state.notation_note("maya", {"action": "on", "pitch": 66, "velocity": 90, "showTimeSeconds": 0.0})
        state.notation_note("maya", {"action": "off", "pitch": 66, "showTimeSeconds": 0.5})
        state.patch_show({"key": "D"})
        xml = state.notation_musicxml("maya")
        self.assertIn('<score-partwise version="4.0">', xml)
        self.assertIn("<step>F</step>", xml)
        self.assertIn("<alter>1</alter>", xml)
        self.assertIn("Maya - Keys", xml)

    def test_disabled_notation_does_not_capture(self):
        state = ShowState()
        state.patch_notation_settings("alex", {"enabled": False})
        rev = state.revision
        result = state.notation_note("alex", {"action": "on", "pitch": 60, "showTimeSeconds": 0.0})
        self.assertEqual(result["revision"], rev)
        self.assertEqual(result["notation"]["alex"]["activeNotes"], 0)


if __name__ == "__main__":
    unittest.main()
