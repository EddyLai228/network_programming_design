# utils.py
import struct, json, socket

_MAX = 65536  # 64 KiB

def _recvall(sock: socket.socket, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf

def send_msg(sock: socket.socket, obj: dict):
    body = json.dumps(obj).encode('utf-8')
    if len(body) > _MAX:
        raise ValueError("message too large")
    hdr = struct.pack('!I', len(body))
    # partial write
    to_send = hdr + body
    sent = 0
    while sent < len(to_send):
        n = sock.send(to_send[sent:])
        if n <= 0:
            raise ConnectionError("socket closed on send")
        sent += n

def recv_msg(sock: socket.socket) -> dict:
    # read length
    hdr = _recvall(sock, 4)
    (length,) = struct.unpack('!I', hdr)
    if length <= 0 or length > _MAX:
        raise ValueError("invalid length")
    body = _recvall(sock, length)
    return json.loads(body.decode('utf-8'))
