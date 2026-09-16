import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from session_channel import AuthenticatedSessionChannel,HEADER_SIZE,MAX_PAYLOAD


class SessionChannelTests(unittest.TestCase):
    def pair(self):
        args=(b"root-key","00112233445566778899aabbccddeeff","a"*64,[100,200])
        return (AuthenticatedSessionChannel(*args,send_direction="a2b",receive_direction="b2a"),
                AuthenticatedSessionChannel(*args,send_direction="b2a",receive_direction="a2b"))

    def test_authenticated_frame_scope_and_replay(self):
        a,b=self.pair();frame=a.encode(100,b"hello");decoded=b.decode(frame)
        self.assertEqual(decoded["payload"],b"hello");self.assertTrue(decoded["authenticated"]);self.assertFalse(decoded["confidential"])
        with self.assertRaisesRegex(ValueError,"replayed"):b.decode(frame)
        with self.assertRaises(PermissionError):a.encode(999,b"blocked")
        with self.assertRaises(ValueError):a.encode(100,b"x"*(MAX_PAYLOAD+1))

    def test_tampering_rotation_and_grace(self):
        a,b=self.pair();frame=bytearray(a.encode(100,b"hello"));frame[-1]^=1
        with self.assertRaisesRegex(ValueError,"authentication"):b.decode(bytes(frame))
        a.rotate(2);b.rotate(2);rotated=a.encode(100,b"new-key");self.assertEqual(b.decode(rotated)["keyEpoch"],2)

    def test_authenticated_checkpoint_reconnect(self):
        a,b=self.pair();b.decode(a.encode(100,b"one"));checkpoint=b.checkpoint()
        _,restored=self.pair();restored.restore(checkpoint);self.assertEqual(restored.status()["inboundSequence"],1)
        tampered=dict(checkpoint);tampered["inboundSequence"]=0
        with self.assertRaisesRegex(ValueError,"authentication"):restored.restore(tampered)

    def test_malformed_header_is_rejected(self):
        _,b=self.pair()
        with self.assertRaisesRegex(ValueError,"truncated"):b.decode(b"x"*(HEADER_SIZE-1))

if __name__=="__main__":unittest.main()
