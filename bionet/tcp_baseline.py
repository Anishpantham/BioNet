"""Length-framed streaming TCP comparison with verified completion."""
import json
import os
import socket
import struct
import time
import uuid
from pathlib import Path
from .integrity import digest
from .receiver import metadata

def exact(sock, n):
    result = bytearray()
    while len(result) < n:
        chunk = sock.recv(n - len(result))
        if not chunk:
            raise ConnectionError('interrupted stream')
        result.extend(chunk)
    return bytes(result)

def send(file, host='127.0.0.1', port=9001):
    path = Path(file); size = path.stat().st_size
    m = dict(filename=path.name, size=size, chunk=1024, count=(size+1023)//1024, window=1, sha256=digest(path))
    payload = json.dumps(m).encode(); start = time.monotonic()
    with socket.create_connection((host, port), timeout=30) as sock, path.open('rb') as stream:
        sock.sendall(struct.pack('!I', len(payload)) + payload)
        for chunk in iter(lambda: stream.read(65536), b''):
            sock.sendall(chunk)
        if exact(sock, 4) != b'PASS':
            raise RuntimeError('receiver rejected file')
    elapsed = time.monotonic() - start
    return dict(seconds=elapsed, goodput_mbps=size*8/elapsed/1e6, success=True, sha256=True)

def receive(host='127.0.0.1', port=9001, output='received', stop=None, ready=None):
    root = Path(output); root.mkdir(parents=True, exist_ok=True)
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port)); listener.listen(4); listener.settimeout(.1)
        if ready:
            ready(listener.getsockname()[1])
        while stop is None or not stop.is_set():
            try:
                sock, _ = listener.accept()
            except socket.timeout:
                continue
            temp = root / ('.' + uuid.uuid4().hex + '.part')
            with sock:
                sock.settimeout(10)
                try:
                    length = struct.unpack('!I', exact(sock, 4))[0]
                    if length > 1200:
                        raise ValueError('metadata too large')
                    m = metadata(exact(sock, length), 1 << 40)
                    with temp.open('xb') as stream:
                        remaining = m['size']
                        while remaining:
                            data = exact(sock, min(65536, remaining)); stream.write(data); remaining -= len(data)
                    if digest(temp) != m['sha256']:
                        raise ValueError('SHA256 mismatch')
                    os.link(temp, root / m['filename'])
                    sock.sendall(b'PASS')
                except (ValueError, KeyError, TypeError, OSError):
                    try:
                        sock.sendall(b'FAIL')
                    except OSError:
                        pass
                finally:
                    temp.unlink(missing_ok=True)
