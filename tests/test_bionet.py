import os
import queue
import threading
import time
import pytest
from bionet.protocol import *
from bionet import sender, receiver, tcp_baseline
from bionet.integrity import digest

@pytest.mark.parametrize('kind', range(1, 8))
def test_codec(kind):
    sid = bytes(16)
    assert decode(encode(kind, sid, 17, b'\x00\xff')) == (kind, sid, 17, b'\x00\xff')

@pytest.mark.parametrize('raw', [b'', b'bad', encode(DATA, bytes(16))[:-1], b'X'+encode(DATA, bytes(16))[1:]])
def test_bad_packet(raw):
    with pytest.raises(ValueError):
        decode(raw)

@pytest.mark.parametrize('size', [0, 1, 1024, 1025, 1048576])
@pytest.mark.parametrize('loss', [0, .2])
def test_udp(tmp_path, size, loss):
    source = tmp_path/'file.bin'; source.write_bytes(os.urandom(size))
    stop = threading.Event(); ports = queue.Queue()
    thread = threading.Thread(target=receiver.receive, kwargs=dict(port=0, output=tmp_path/'out', stop=stop, ready=ports.put, loss=loss, reorder=.2, seed=7, window_size=8))
    thread.start()
    try:
        port = ports.get(timeout=3)
        result = sender.send(source, port=port, loss=loss, reorder=.3, corruption=.02, window_size=32, timeout=.05)
        assert result['sha256']
        assert digest(source) == digest(tmp_path/'out'/'file.bin')
        with pytest.raises(RuntimeError, match='destination'):
            sender.send(source, port=port)
    finally:
        stop.set(); thread.join(3)
    assert not thread.is_alive()

def test_retry_exhaustion(tmp_path):
    file = tmp_path/'empty'; file.touch()
    with pytest.raises(TimeoutError):
        sender.send(file, port=1, retries=1, timeout=.01, loss=1)

def test_tcp(tmp_path):
    source = tmp_path/'binary'; source.write_bytes(os.urandom(100000))
    stop = threading.Event(); ports = queue.Queue()
    thread = threading.Thread(target=tcp_baseline.receive, kwargs=dict(port=0, output=tmp_path/'out', stop=stop, ready=ports.put))
    thread.start()
    try:
        assert tcp_baseline.send(source, port=ports.get(timeout=3))['sha256']
        assert digest(source) == digest(tmp_path/'out'/'binary')
    finally:
        stop.set(); thread.join(3)

@pytest.mark.parametrize('change', [{'filename':'../escape'}, {'chunk':0}, {'size':-1}, {'window':5000}, {'sha256':'bad'}, {'count':2}, {'size':True}])
def test_metadata_limits(change):
    import json
    m = dict(filename='safe', size=0, chunk=1024, count=0, window=32, sha256='0'*64)
    m.update(change)
    with pytest.raises(ValueError):
        receiver.metadata(json.dumps(m).encode(), 1000)

@pytest.mark.parametrize('dropped_kind', [START, START_ACK, FIN, FIN_ACK])
def test_lost_controls(tmp_path, monkeypatch, dropped_kind):
    from bionet.impairment import Channel
    original = Channel.send; dropped = []
    def send(self, packet, address):
        if decode(packet)[0] == dropped_kind and not dropped:
            dropped.append(True)
            return
        original(self, packet, address)
    monkeypatch.setattr(Channel, 'send', send)
    test_udp(tmp_path, 2048, 0)
    assert dropped

def test_duplicate_data(tmp_path, monkeypatch):
    from bionet.impairment import Channel
    original = Channel.send
    def send(self, packet, address):
        original(self, packet, address)
        if decode(packet)[0] in (DATA, ACK):
            original(self, packet, address)
    monkeypatch.setattr(Channel, 'send', send)
    test_udp(tmp_path, 8192, 0)

@pytest.mark.parametrize('mismatch', [False, True])
def test_interrupted_and_hash_failure(tmp_path, mismatch):
    import json
    import socket
    stop = threading.Event(); ports = queue.Queue()
    thread = threading.Thread(target=receiver.receive, kwargs=dict(port=0, output=tmp_path, stop=stop, ready=ports.put, idle_timeout=.05))
    thread.start()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1); peer = ('127.0.0.1', ports.get(timeout=3)); sid = bytes(16)
            m = dict(filename='bad', size=1, chunk=1, count=1, window=1, sha256='0'*64)
            sock.sendto(encode(START, sid, payload=json.dumps(m).encode()), peer)
            assert decode(sock.recv(2048))[0] == START_ACK
            sock.sendto(encode(DATA, b'x'*16, payload=b'a'), peer)
            if mismatch:
                sock.sendto(encode(DATA, sid, payload=b'a'), peer)
                assert decode(sock.recv(2048))[0] == ACK
                sock.sendto(encode(FIN, sid), peer)
                assert decode(sock.recv(2048))[0] == ERROR
            time.sleep(.1)
            assert not list(tmp_path.iterdir())
    finally:
        stop.set(); thread.join(3)

def test_sequential_transfers(tmp_path):
    stop = threading.Event(); ports = queue.Queue()
    thread = threading.Thread(target=receiver.receive, kwargs=dict(port=0, output=tmp_path/'out', stop=stop, ready=ports.put))
    thread.start()
    try:
        port = ports.get(timeout=3)
        for name in ('first', 'second'):
            source = tmp_path/name; source.write_bytes(os.urandom(10000))
            assert sender.send(source, port=port)['success']
            assert source.read_bytes() == (tmp_path/'out'/name).read_bytes()
    finally:
        stop.set(); thread.join(3)
