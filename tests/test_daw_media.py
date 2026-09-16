import math,struct,sys,tempfile,unittest,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from daw_media import inspect_wav,resolve_media_path
class DawMediaTests(unittest.TestCase):
 def test_wav_hash_and_peaks(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/"tone.wav"
   with wave.open(str(path),"wb") as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b"".join(struct.pack("<h",round(math.sin(i/5)*20000)) for i in range(480)))
   media=inspect_wav(path,peak_buckets=16);self.assertEqual(media["sourceSampleRate"],48000);self.assertEqual(media["canonicalFrames"],1920);self.assertEqual(len(media["waveform"]["buckets"]),16);self.assertFalse(media["physicalOutputsArmed"])
 def test_media_root_escape_fails(self):
  with tempfile.TemporaryDirectory() as raw:
   root=Path(raw)/"media";root.mkdir();outside=Path(raw)/"outside.wav";outside.write_bytes(b"x")
   with self.assertRaises(PermissionError):resolve_media_path(root,"../outside.wav")
if __name__=="__main__":unittest.main()
