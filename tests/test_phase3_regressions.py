"""Deterministic regressions for defects confirmed during the Phase 3 audit."""
import hashlib
import json
import socket
import struct
import sys
import time
import uuid
from pathlib import Path

import pytest
from bionet import receiver, sender, tcp_baseline
from bionet.benchmark import local_receiver
from bionet.impairment import Channel
from bionet.protocol import *


def meta(data=b'', **changes):
    m = dict(filename='safe.bin', size=len(data), chunk=1024,
             count=(len(data)+1023)//1024, window=8,
             sha256=hashlib.sha256(data).hexdigest())
    m.update(changes)
    return json.dumps(m).encode()


def udp_peer(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(('127.0.0.1', port)); sock.settimeout(.2)
    return sock


@pytest.fixture
def shallow_recursion():
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(500)
    yield
    sys.setrecursionlimit(old)


@pytest.mark.parametrize('payload', [b'['*1100+b']', meta(extra='x'*1200)])
def test_metadata_bounded_parser(payload, shallow_recursion):
    with pytest.raises(ValueError):
        receiver.metadata(payload, MAX_FILE_SIZE)


def test_deep_metadata_does_not_kill_udp(tmp_path, shallow_recursion):
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sock.send(encode(START, bytes(16), payload=b'['*1100+b']'))
        assert decode(sock.recv(2048))[0] == ERROR
        sock.send(encode(START, b'x'*16, payload=meta()))
        assert decode(sock.recv(2048))[0] == START_ACK


@pytest.mark.parametrize('seq', [True, 1.5, -1, 1 << 64])
def test_sequence_type(seq):
    with pytest.raises(ValueError):
        encode(DATA, bytes(16), seq)


@pytest.mark.parametrize('field', ['latency', 'jitter'])
@pytest.mark.parametrize('value', [float('nan'), float('inf')])
def test_finite_scheduler(field, value):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        with pytest.raises(ValueError):
            Channel(sock, **{field: value})


@pytest.mark.parametrize('field,value', [('timeout', float('nan')), ('timeout', float('inf')),
                                        ('window_size', 1.5), ('retries', 1.5)])
def test_sender_rejects_invalid_limits_before_io(tmp_path, field, value):
    with pytest.raises(ValueError):
        sender.send(tmp_path/'missing', **{field:value})


def test_udp_disk_write_failure_keeps_service_alive(tmp_path, monkeypatch):
    original = Path.open
    class FailingWriter:
        def __init__(self, stream): self.stream = stream
        def write(self, data): raise OSError('injected ENOSPC')
        def close(self): self.stream.close()
        @property
        def closed(self): return self.stream.closed
    def opened(path, mode='r', *args, **kwargs):
        stream = original(path, mode, *args, **kwargs)
        return FailingWriter(stream) if mode == 'xb' and path.suffix == '.part' else stream
    monkeypatch.setattr(Path, 'open', opened)
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sid = bytes(16)
        sock.send(encode(START, sid, payload=meta(b'x')))
        assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(DATA, sid, payload=b'x'))
        # An ACK can precede the error; publication must never be confirmed.
        answer = decode(sock.recv(2048))
        if answer[0] == ACK: answer = decode(sock.recv(2048))
        assert answer[0] == ERROR
        sock.send(encode(START, b'y'*16, payload=meta()))
        assert decode(sock.recv(2048))[0] == START_ACK
    assert not list(tmp_path.glob('*.part'))


def test_tcp_does_not_delete_unowned_partial(tmp_path, monkeypatch):
    fixed = uuid.UUID(int=0)
    monkeypatch.setattr(tcp_baseline.uuid, 'uuid4', lambda: fixed)
    partial = tmp_path/('.'+fixed.hex+'.part'); partial.write_bytes(b'preexisting')
    with local_receiver('tcp', tmp_path) as port:
        with socket.create_connection(('127.0.0.1', port), timeout=1) as sock:
            payload = meta(); sock.sendall(struct.pack('!I', len(payload))+payload)
            assert tcp_baseline.exact(sock, 4) == b'FAIL'
    assert partial.read_bytes() == b'preexisting'


def test_deep_metadata_does_not_kill_tcp(tmp_path, shallow_recursion):
    with local_receiver('tcp', tmp_path/'out') as port:
        with socket.create_connection(('127.0.0.1', port), timeout=1) as sock:
            payload = b'['*1100+b']'
            sock.sendall(struct.pack('!I', len(payload))+payload)
            assert tcp_baseline.exact(sock, 4) == b'FAIL'
        source = tmp_path/'source'; source.touch()
        assert tcp_baseline.send(source, port=port)['success']


def test_udp_releases_temp_ownership_after_completion(tmp_path):
    sid = bytes(16)
    partial = tmp_path/('.'+sid.hex()+'.part')
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sock.send(encode(START, sid, payload=meta()))
        assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(FIN, sid)); assert decode(sock.recv(2048))[0] == FIN_ACK
        partial.write_bytes(b'new owner')
    assert partial.read_bytes() == b'new owner'


@pytest.mark.parametrize('kind', [START, FIN])
def test_nonzero_control_sequence_ignored(tmp_path, kind):
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sid = bytes(16)
        if kind == FIN:
            sock.send(encode(START, sid, payload=meta()))
            assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(kind, sid, seq=99, payload=meta() if kind == START else b''))
        with pytest.raises(socket.timeout): sock.recv(2048)
        assert not (tmp_path/'safe.bin').exists()


@pytest.mark.parametrize('change', ['seq', 'payload'])
def test_sender_ignores_malformed_fin_ack(tmp_path, monkeypatch, change):
    original = Channel.send
    def corrupt_ack(channel, packet, address):
        kind, sid, seq, payload = decode(packet)
        if kind == FIN_ACK:
            packet = encode(kind, sid, 9 if change == 'seq' else 0,
                            b'extra' if change == 'payload' else b'')
        return original(channel, packet, address)
    monkeypatch.setattr(Channel, 'send', corrupt_ack)
    source = tmp_path/'source'; source.touch()
    with local_receiver('udp', tmp_path/'out', quiet=True) as port:
        with pytest.raises(TimeoutError, match='control'):
            sender.send(source, port=port, retries=1, timeout=.01)
    # Publication happened, but no valid confirmation reached the sender.
    assert (tmp_path/'out'/'source').exists()


def test_duplicate_start_conflict(tmp_path):
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sid = bytes(16)
        sock.send(encode(START, sid, payload=meta()))
        assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(START, sid, payload=meta(filename='different')))
        assert decode(sock.recv(2048))[0] == ERROR
        sock.send(encode(FIN, sid)); assert decode(sock.recv(2048))[0] == FIN_ACK
    assert (tmp_path/'safe.bin').exists() and not (tmp_path/'different').exists()


def test_invalid_session_traffic_does_not_extend_idle_timeout(tmp_path):
    with local_receiver('udp', tmp_path, quiet=True, idle_timeout=.05) as port, udp_peer(port) as sock:
        sid = bytes(16)
        sock.send(encode(START, sid, payload=meta(b'x')))
        assert decode(sock.recv(2048))[0] == START_ACK
        until = time.monotonic()+.15
        while time.monotonic() < until:
            sock.send(encode(DATA, sid, MAX_SEQUENCE, b'bad'))
            time.sleep(.01)
        assert not list(tmp_path.glob('*.part'))


def test_udp_flush_failure_keeps_service_alive(tmp_path, monkeypatch):
    original = Path.open
    class FailClose:
        def __init__(self, stream): self.stream = stream
        def write(self, data): return self.stream.write(data)
        def close(self):
            self.stream.close()
            raise OSError('injected flush failure')
        @property
        def closed(self): return self.stream.closed
    def opened(path, mode='r', *args, **kwargs):
        stream = original(path, mode, *args, **kwargs)
        return FailClose(stream) if mode == 'xb' and path.suffix == '.part' else stream
    monkeypatch.setattr(Path, 'open', opened)
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sock.send(encode(START, bytes(16), payload=meta()))
        assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(FIN, bytes(16)))
        assert decode(sock.recv(2048))[0] == ERROR
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('change', [dict(window_size=1.5), dict(idle_timeout=float('nan')),
                                     dict(idle_timeout=float('inf')), dict(max_size=True)])
def test_receiver_invalid_limits_before_io(tmp_path, change):
    with pytest.raises(ValueError): receiver.receive(output=tmp_path/'unused', **change)
    assert not (tmp_path/'unused').exists()


def test_sender_ignores_nonzero_start_ack(tmp_path, monkeypatch):
    original = Channel.send
    def malformed(channel, packet, peer):
        kind, sid, seq, payload = decode(packet)
        if kind == START_ACK: packet = encode(kind, sid, 1, payload)
        return original(channel, packet, peer)
    monkeypatch.setattr(Channel, 'send', malformed)
    source = tmp_path/'source'; source.touch()
    with local_receiver('udp', tmp_path/'out', quiet=True) as port:
        with pytest.raises(TimeoutError, match='control'):
            sender.send(source, port=port, retries=1, timeout=.01)
    assert not list((tmp_path/'out').iterdir())


def test_sender_ignores_payload_bearing_ack(tmp_path, monkeypatch):
    original = Channel.send; malformed = False
    def intercept(channel, packet, peer):
        nonlocal malformed
        kind, sid, seq, payload = decode(packet)
        if kind == ACK and not malformed:
            malformed = True; packet = encode(kind, sid, seq, b'unexpected')
        return original(channel, packet, peer)
    monkeypatch.setattr(Channel, 'send', intercept)
    source = tmp_path/'source'; source.write_bytes(b'x')
    with local_receiver('udp', tmp_path/'out', quiet=True) as port:
        result = sender.send(source, port=port, retries=2, timeout=.03)
    assert result['retransmissions'] == 1 and result['acknowledged_packets'] == 1


def test_repeated_start_refreshes_idle_without_resetting_progress(tmp_path):
    sid = bytes(16); payload = meta(b'ab', chunk=1, count=2)
    with local_receiver('udp', tmp_path, quiet=True, idle_timeout=.12) as port, udp_peer(port) as sock:
        sock.send(encode(START, sid, payload=payload))
        assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(DATA, sid, 0, b'a')); assert decode(sock.recv(2048))[0] == ACK
        for _ in range(4):
            time.sleep(.05)
            sock.send(encode(START, sid, payload=payload))
            assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(DATA, sid, 1, b'b')); assert decode(sock.recv(2048))[0] == ACK
        sock.send(encode(FIN, sid)); assert decode(sock.recv(2048))[0] == FIN_ACK
    assert (tmp_path/'safe.bin').read_bytes() == b'ab'
