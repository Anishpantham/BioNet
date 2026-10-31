"""Synthetic, bounded localhost protocol and fault-injection validation."""
from collections import Counter
import hashlib
import json
import random
import socket
import struct
import threading
import time
import zipfile
import zlib

import pytest
from bionet import receiver, sender, tcp_baseline
from bionet.benchmark import local_receiver, synthetic, run, summarize
from bionet.dashboard import Dashboard
from bionet.impairment import Channel
from bionet.integrity import digest
from bionet.protocol import *
from test_phase3_regressions import meta, udp_peer


def checked_transfer(tmp_path, size=8193, protocol='udp', tx=None, rx=None):
    source = tmp_path/'synthetic.bin'; synthetic(source, size)
    out = tmp_path/'out'
    options = dict(quiet=True) if protocol == 'udp' else {}
    options.update(rx or {})
    with local_receiver(protocol, out, **options) as port:
        send = sender.send if protocol == 'udp' else tcp_baseline.send
        options = dict(timeout=.03, retries=30) if protocol == 'udp' else {}
        options.update(tx or {})
        result = send(source, port=port, **options)
    assert result['success'] and result['sha256']
    assert digest(source) == digest(out/source.name)
    assert result['goodput_mbps'] == pytest.approx(size*8/result['seconds']/1e6)
    assert not list(out.glob('*.part'))
    return result


@pytest.mark.parametrize('protocol', ['udp', 'tcp'])
@pytest.mark.parametrize('size', [0, 1, 1023, 1024, 1025, 65536, 1<<20, 10<<20])
def test_file_boundaries(tmp_path, protocol, size):
    checked_transfer(tmp_path, size=size, protocol=protocol)


@pytest.mark.parametrize('window', [1, 2, 8, 32, 64, 128])
def test_windows(tmp_path, window):
    checked_transfer(tmp_path, size=65537,
                     tx=dict(window_size=window), rx=dict(window_size=window))


@pytest.mark.parametrize('loss', [0, .05, .1, .2, .3, .4])
@pytest.mark.parametrize('direction', ['sender', 'receiver', 'both'])
def test_seeded_loss(tmp_path, loss, direction):
    tx = dict(loss=loss if direction != 'receiver' else 0, seed=42)
    rx = dict(loss=loss if direction != 'sender' else 0, seed=73)
    checked_transfer(tmp_path, tx=tx, rx=rx)


@pytest.mark.parametrize('fault', [dict(corruption=.3), dict(reorder=.8),
    dict(latency=.005, jitter=.003), dict(loss=.2, corruption=.1, reorder=.4, latency=.002, jitter=.001)])
def test_impairments(tmp_path, fault):
    checked_transfer(tmp_path, size=32769, tx=dict(fault, seed=12), rx=dict(fault, seed=54))


@pytest.mark.parametrize('protocol', ['udp', 'tcp'])
def test_zip_and_seeded_binary(tmp_path, protocol):
    source = tmp_path/'synthetic.zip'
    rng = random.Random(19)
    with zipfile.ZipFile(source, 'x', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('synthetic.bin', b'\x00'*100+rng.randbytes(65537))
    with local_receiver(protocol, tmp_path/'out', **(dict(quiet=True) if protocol == 'udp' else {})) as port:
        send = sender.send if protocol == 'udp' else tcp_baseline.send
        assert send(source, port=port)['success']
    assert digest(source) == digest(tmp_path/'out'/source.name)
    with zipfile.ZipFile(tmp_path/'out'/source.name) as archive:
        assert archive.testzip() is None


@pytest.mark.parametrize('field,value', [('magic', b'FAIL'), ('version', 2), ('kind', 0),
                                       ('kind', 8), ('length', 1201)])
def test_header_semantics_with_valid_crc(field, value):
    fields = dict(magic=b'BNET', version=1, kind=DATA, session=bytes(16), seq=0, length=0)
    fields[field] = value
    raw = HEADER.pack(*fields.values())
    with pytest.raises(ValueError): decode(raw+struct.pack('!I', zlib.crc32(raw)))


@pytest.mark.parametrize('cut', [0, 1, 5, 31, 32, 35, 40])
def test_truncated_datagrams(cut):
    raw = encode(DATA, bytes(16), payload=b'abcdef')
    with pytest.raises(ValueError): decode(raw[:cut])


def test_crc_every_byte_and_oversize():
    packet = encode(DATA, bytes(16), MAX_SEQUENCE, b'\x00\xff'*600)
    assert decode(packet)[2] == MAX_SEQUENCE
    for i in range(len(packet)):
        raw = bytearray(packet); raw[i] ^= 1
        with pytest.raises(ValueError): decode(raw)
    with pytest.raises(ValueError): encode(DATA, bytes(16), payload=b'x'*1201)
    with pytest.raises(ValueError): decode(packet+b'extra')
    with pytest.raises(ValueError): encode(DATA, b'short')


@pytest.mark.parametrize('name', ['', '.', '..', '../escape', '/absolute', 'a/b', 'a\\b', 'a\0b', 'x'*201, '\ud800'])
def test_unsafe_filename(name):
    with pytest.raises(ValueError): receiver.metadata(meta(filename=name), MAX_FILE_SIZE)


@pytest.mark.parametrize('changes', [dict(chunk=0), dict(chunk=1025), dict(window=0),
    dict(window=4097), dict(size=-1), dict(size=MAX_FILE_SIZE+1), dict(count=MAX_SEQUENCE+1),
    dict(count=-1), dict(size=True), dict(window=1.2), dict(sha256='G'*64), dict(sha256=3)])
def test_metadata_resources(changes):
    with pytest.raises(ValueError): receiver.metadata(meta(**changes), MAX_FILE_SIZE)


@pytest.mark.parametrize('loss_kind', [DATA, ACK])
def test_only_missing_packet_retransmits(tmp_path, monkeypatch, loss_kind):
    original = Channel.send; seen = Counter(); trace = []; dropped = False
    def intercept(channel, packet, peer):
        nonlocal dropped
        kind, sid, seq, payload = decode(packet)
        if kind == DATA: seen[seq] += 1; trace.append(seq)
        if kind == loss_kind and seq == 1 and not dropped:
            dropped = True
            return False
        # Duplicate ACKs and unrelated, out-of-window ACKs use real sockets.
        if kind == ACK:
            original(channel, encode(ACK, b'?'*16, seq), peer)
            original(channel, encode(ACK, sid, MAX_SEQUENCE), peer)
            original(channel, packet, peer)
        return original(channel, packet, peer)
    monkeypatch.setattr(Channel, 'send', intercept)
    result = checked_transfer(tmp_path, size=8192,
        tx=dict(window_size=4, timeout=.1), rx=dict(window_size=4))
    assert dropped and result['retransmissions'] == 1
    assert seen == Counter({i:2 if i == 1 else 1 for i in range(8)})
    # With base stalled at 1, sequence 5 must wait for the missing ACK.
    assert trace.index(5) > trace.index(1, trace.index(1)+1)


def test_independent_timers(tmp_path, monkeypatch):
    original = Channel.send; calls = {}
    def intercept(channel, packet, peer):
        kind, sid, seq, payload = decode(packet)
        if kind == DATA:
            calls.setdefault(seq, []).append(time.monotonic())
            if len(calls[seq]) == 1 and seq in (0, 2): return False
        return original(channel, packet, peer)
    monkeypatch.setattr(Channel, 'send', intercept)
    checked_transfer(tmp_path, size=4096, tx=dict(timeout=.1, window_size=4))
    assert {seq:len(times) for seq,times in calls.items()} == {0:2, 1:1, 2:2, 3:1}
    assert all(.09 <= calls[i][1]-calls[i][0] < .5 for i in (0, 2))


def test_receiver_window_duplicates_and_early_fin(tmp_path):
    data = b'abc'; sid = bytes(16)
    with local_receiver('udp', tmp_path, window_size=2, quiet=True) as port, udp_peer(port) as sock:
        def send(kind, seq=0, payload=b''):
            sock.send(encode(kind, sid, seq, payload))
        send(START, payload=meta(data, chunk=1, count=3, window=128))
        assert decode(sock.recv(2048))[3] == b'2'
        send(DATA, 2, b'c')
        with pytest.raises(socket.timeout): sock.recv(2048)
        send(DATA, 1, b'b'); assert decode(sock.recv(2048))[2] == 1
        send(START, payload=meta(data, chunk=1, count=3, window=128))
        assert decode(sock.recv(2048))[0] == START_ACK
        send(FIN)
        with pytest.raises(socket.timeout): sock.recv(2048)
        send(DATA, 0, b'a'); assert decode(sock.recv(2048))[2] == 0
        send(DATA, 1, b'b'); assert decode(sock.recv(2048))[2] == 1
        send(DATA, MAX_SEQUENCE, b'x')
        with pytest.raises(socket.timeout): sock.recv(2048)
        send(DATA, 2, b'c'); assert decode(sock.recv(2048))[2] == 2
        send(FIN); assert decode(sock.recv(2048))[0] == FIN_ACK
        send(FIN); assert decode(sock.recv(2048))[0] == FIN_ACK
        send(DATA, 0, b'a')
        with pytest.raises(socket.timeout): sock.recv(2048)
    assert (tmp_path/'safe.bin').read_bytes() == data


def test_sessions_concurrency_and_unrelated_traffic(tmp_path):
    with local_receiver('udp', tmp_path, quiet=True, idle_timeout=.15) as port, udp_peer(port) as a, udp_peer(port) as b:
        a.send(encode(START, bytes(16), payload=meta(b'x')))
        assert decode(a.recv(2048))[0] == START_ACK
        b.send(encode(START, b'b'*16, payload=meta()))
        assert decode(b.recv(2048))[0] == ERROR
        b.send(encode(DATA, bytes(16), payload=b'x'))  # same SID, wrong address
        a.send(encode(DATA, b'b'*16, payload=b'x'))   # right address, wrong SID
        a.send(b'unrelated UDP garbage')
        time.sleep(.25)
        assert not list(tmp_path.glob('*.part'))
        b.send(encode(START, b'b'*16, payload=meta()))
        assert decode(b.recv(2048))[0] == START_ACK
        b.send(encode(FIN, b'b'*16)); assert decode(b.recv(2048))[0] == FIN_ACK


def test_receiver_restart_rejects_stale_data(tmp_path):
    sid = bytes(16)
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sock.send(encode(START, sid, payload=meta(b'x')))
        assert decode(sock.recv(2048))[0] == START_ACK
    assert not list(tmp_path.iterdir())
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sock.send(encode(DATA, sid, payload=b'x'))
        sock.send(encode(FIN, sid))
        with pytest.raises(socket.timeout): sock.recv(2048)
    assert not list(tmp_path.iterdir())


def test_data_retry_exhaustion_and_cleanup(tmp_path, monkeypatch):
    original = Channel.send
    def no_data(channel, packet, peer):
        return False if decode(packet)[0] == DATA else original(channel, packet, peer)
    monkeypatch.setattr(Channel, 'send', no_data)
    source = tmp_path/'x'; source.write_bytes(b'x')
    with local_receiver('udp', tmp_path/'out', quiet=True, idle_timeout=.05) as port:
        with pytest.raises(TimeoutError, match='DATA 0'):
            sender.send(source, port=port, timeout=.01, retries=2)
        time.sleep(.1)
        assert not list((tmp_path/'out').iterdir())


@pytest.mark.parametrize('protocol', ['udp', 'tcp'])
def test_shortened_source(tmp_path, monkeypatch, protocol):
    source = tmp_path/'source'; source.write_bytes(b'x'*4096)
    module = sender if protocol == 'udp' else tcp_baseline
    original = module.digest
    def truncate(path):
        value = original(path); source.write_bytes(b''); return value
    monkeypatch.setattr(module, 'digest', truncate)
    with local_receiver(protocol, tmp_path/'out', **(dict(quiet=True) if protocol == 'udp' else {})) as port:
        with pytest.raises(OSError, match='source shortened'):
            module.send(source, port=port)
    assert not list((tmp_path/'out').iterdir())


@pytest.mark.parametrize('protocol', ['udp', 'tcp'])
def test_no_clobber_symlink(tmp_path, protocol):
    out = tmp_path/'out'; out.mkdir()
    external = tmp_path/'protected'; external.write_bytes(b'protected')
    (out/'source').symlink_to(external)
    source = tmp_path/'source'; source.write_bytes(b'different')
    with local_receiver(protocol, out, **(dict(quiet=True) if protocol == 'udp' else {})) as port:
        with pytest.raises(RuntimeError):
            (sender.send if protocol == 'udp' else tcp_baseline.send)(source, port=port)
    assert external.read_bytes() == b'protected'
    assert (out/'source').is_symlink()


def test_tcp_partial_frames_and_disconnect(tmp_path):
    data = b'\x00abc'*100
    with local_receiver('tcp', tmp_path) as port:
        with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
            payload = meta(data)
            frame = struct.pack('!I', len(payload))+payload+data
            for byte in frame: sock.sendall(bytes([byte]))
            assert tcp_baseline.exact(sock, 4) == b'PASS'
        with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
            payload = meta(data, filename='interrupted')
            sock.sendall(struct.pack('!I', len(payload))+payload+data[:2])
        # Next connection proves recovery after EOF mid-file.
        with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
            sock.sendall(struct.pack('!I', 1201))
            assert tcp_baseline.exact(sock, 4) == b'FAIL'
    assert (tmp_path/'safe.bin').read_bytes() == data
    assert not (tmp_path/'interrupted').exists()
    assert not list(tmp_path.glob('*.part'))


def test_channel_real_socket_schedule_and_counters():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rx, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tx:
        rx.bind(('127.0.0.1', 0)); rx.settimeout(.01)
        channel = Channel(tx, latency=.04, corruption=1, seed=4)
        raw = encode(DATA, bytes(16), payload=b'x')
        started = time.monotonic(); channel.send(raw, rx.getsockname())
        assert time.monotonic()-started < .03
        assert channel.packets_sent == 0 and len(channel.queue) == 1
        with pytest.raises(socket.timeout): rx.recv(2048)
        time.sleep(.04); channel.flush()
        with pytest.raises(ValueError, match='CRC'): decode(rx.recv(2048))
        assert channel.sent == channel.packets_sent == 1 and channel.bytes_sent == len(raw)
        channel.loss = 1; assert channel.send(raw, rx.getsockname()) is False
        assert channel.sent == 2 and channel.drops == 1 and channel.packets_sent == 1
        channel.loss = 0; channel.latency = 100
        channel.queue = [(time.monotonic()+100, i, raw, rx.getsockname()) for i in range(65536)]
        with pytest.raises(RuntimeError, match='resource limit'): channel.send(raw, rx.getsockname())


def test_seeded_channel_repeatability():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        a = Channel(sock, loss=.3, latency=100, jitter=.01, reorder=.5, corruption=.2, seed=99)
        b = Channel(sock, loss=.3, latency=100, jitter=.01, reorder=.5, corruption=.2, seed=99)
        packets = [encode(DATA, bytes(16), i, b'x') for i in range(100)]
        assert [a.send(p, ('127.0.0.1', 1)) for p in packets] == [b.send(p, ('127.0.0.1', 1)) for p in packets]
        assert a.drops == b.drops
        assert sorted((i,p) for _,i,p,_ in a.queue) == sorted((i,p) for _,i,p,_ in b.queue)


def test_dashboard_no_color_empty_and_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('NO_COLOR', '1')
    result = checked_transfer(tmp_path, size=0, tx=dict(dashboard=True))
    assert result['acknowledged_packets'] == 0
    stderr = capsys.readouterr().err
    assert 'PASS' in stderr and '100.00%' in stderr and '\x1b[' not in stderr
    with pytest.raises(TimeoutError), Dashboard(True) as display:
        display.update(force=True, status='testing')
        raise TimeoutError('injected')
    assert display.state['verified'] == 'Not confirmed'


def test_benchmark_preserves_failures(tmp_path, monkeypatch):
    def fail(*args, **kwargs): raise TimeoutError('injected transfer timeout')
    monkeypatch.setattr(sender, 'send', fail)
    rows = run(tmp_path, trials=3, sizes=(1024,), windows=(1,), losses=(0,), no_plots=True)
    assert len(rows) == 9
    assert sum(not r['success'] for r in rows) == 6
    assert sum(r['failures'] for r in summarize(rows)) == 6
    assert all('injected' in r['error'] and r['failure_seconds'] > 0 for r in rows if not r['success'])


@pytest.mark.parametrize('protocol', ['udp', 'tcp'])
def test_publish_failure_cleanup(tmp_path, monkeypatch, protocol):
    import os
    def denied(*args, **kwargs): raise OSError('injected link failure')
    monkeypatch.setattr(os, 'link', denied)
    source = tmp_path/'source'; source.write_bytes(b'x')
    with local_receiver(protocol, tmp_path/'out', **(dict(quiet=True) if protocol == 'udp' else {})) as port:
        with pytest.raises(RuntimeError):
            (sender.send if protocol == 'udp' else tcp_baseline.send)(source, port=port)
    assert not list((tmp_path/'out').iterdir())


def test_destination_created_during_transfer(tmp_path):
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        sock.send(encode(START, bytes(16), payload=meta()))
        assert decode(sock.recv(2048))[0] == START_ACK
        (tmp_path/'safe.bin').write_bytes(b'other owner')
        sock.send(encode(FIN, bytes(16))); assert decode(sock.recv(2048))[0] == ERROR
    assert (tmp_path/'safe.bin').read_bytes() == b'other owner'
    assert not list(tmp_path.glob('*.part'))


def test_completed_cache_bound_and_expiration(tmp_path, monkeypatch):
    import types
    original = time.monotonic; offset = [0]
    monkeypatch.setattr(receiver, 'time', types.SimpleNamespace(monotonic=lambda: original()+offset[0]))
    with local_receiver('udp', tmp_path, quiet=True) as port, udp_peer(port) as sock:
        for index in range(1024):
            sid = index.to_bytes(16, 'big')
            sock.send(encode(START, sid, payload=meta(filename=str(index))))
            assert decode(sock.recv(2048))[0] == START_ACK
            sock.send(encode(FIN, sid)); assert decode(sock.recv(2048))[0] == FIN_ACK
        sid = (1024).to_bytes(16, 'big')
        sock.send(encode(START, sid, payload=meta(filename='next')))
        assert decode(sock.recv(2048))[0] == ERROR
        offset[0] = 121
        time.sleep(.02)
        sock.send(encode(FIN, bytes(16)))
        with pytest.raises(socket.timeout): sock.recv(2048)
        sock.send(encode(START, sid, payload=meta(filename='next')))
        assert decode(sock.recv(2048))[0] == START_ACK
        sock.send(encode(FIN, sid)); assert decode(sock.recv(2048))[0] == FIN_ACK
    assert len(list(tmp_path.iterdir())) == 1025
