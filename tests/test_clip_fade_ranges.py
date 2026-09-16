import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from daw_session import render_plan, DawSessionStore
from daw_production import OfflineRenderer
from daw_playback import ArrangementProducer


class ClipFadeRangeTests(unittest.TestCase):
    def test_partial_range_preserves_original_clip_fades(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with wave.open(str(root / "tone.wav"), "wb") as output:
                output.setnchannels(1); output.setsampwidth(2); output.setframerate(48000)
                output.writeframes(b"\x00\x20" * 3000)
            session = {"tracks": [{"trackId": "t", "clips": [{
                "clipId": "c", "startFrame": 137, "lengthFrames": 3000,
                "sourceOffsetFrames": 17, "source": {"type": "audio-file", "uri": "tone.wav"},
                "fades": {"inFrames": 1000, "outFrames": 1000}}]}]}
            renderer = OfflineRenderer(root)
            renderer.render(session, root / "full.wav", 0, 3500, bits=32)
            with wave.open(str(root / "full.wav"), "rb") as full:
                all_pcm = full.readframes(3500)
            producer = ArrangementProducer(None, root)
            full_plan = render_plan(session, 0, 3500)
            for start, end in ((500, 900), (1500, 1800), (2300, 2800)):
                with self.subTest(start=start):
                    plan = render_plan(session, start, end)
                    self.assertEqual(plan["regions"][0]["clipOffsetFrames"], start - 137)
                    self.assertEqual(plan["regions"][0]["clipLengthFrames"], 3000)
                    self.assertEqual(producer._block(plan, start, end-start), producer._block(full_plan, start, end-start))
                    renderer.render(session, root / "part.wav", start, end, bits=32)
                    with wave.open(str(root / "part.wav"), "rb") as part:
                        self.assertEqual(part.readframes(end-start), all_pcm[start*8:end*8])
            store = DawSessionStore(root / "session.json")
            session["revision"] = 1
            store.save(session)
            current_id = "c"
            for index, split in enumerate((500, 1500, 2800)):
                next_id = f"split-{index}"
                edited = store.edit({"op": "split", "clipId": current_id, "expectedRevision": store.load()["revision"], "splitFrame": split, "newClipId": next_id})
                renderer.render(edited, root / "split.wav", 0, 3500, bits=32)
                with wave.open(str(root / "split.wav"), "rb") as result:
                    self.assertEqual(result.readframes(3500), all_pcm)
                self.assertEqual(DawSessionStore(root / "session.json").load(), edited)
                current_id = next_id
