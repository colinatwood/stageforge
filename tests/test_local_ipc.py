import socket,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from local_ipc import recv_frame,send_frame
from session_channel import AuthenticatedSessionChannel,HEADER_SIZE

class LocalIpcTests(unittest.TestCase):
    def channels(self):
        args=(b"k"*32,"11"*16,"22"*32,{7})
        return (AuthenticatedSessionChannel(*args,send_direction="client",receive_direction="server"),AuthenticatedSessionChannel(*args,send_direction="server",receive_direction="client"))
    def test_length_transport_carries_authenticated_frame(self):
        client,server=self.channels();left,right=socket.socketpair()
        with left,right:
            send_frame(left,client.encode(7,b'{"op":"status"}'))
            decoded=server.decode(recv_frame(right));self.assertEqual(decoded["payload"],b'{"op":"status"}')
    def test_rejects_unbounded_length(self):
        left,right=socket.socketpair()
        with left,right:
            left.sendall((999999).to_bytes(4,"big"))
            with self.assertRaises(ValueError):recv_frame(right)

if __name__=="__main__":unittest.main()
