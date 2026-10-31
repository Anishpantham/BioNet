"""Focused Phase 2 smoke checks; stress and exhaustive validation are deferred."""
import csv
import json
import socket
from pathlib import Path
import pytest
from bionet import receiver, sender
from bionet.benchmark import local_receiver, run, summarize, synthetic
from bionet.dashboard import Dashboard
from bionet.impairment import Channel
from bionet.integrity import digest
from bionet.protocol import MAX_SEQUENCE, DATA, encode


def test_sequence_limit():
    encode(DATA, bytes(16), MAX_SEQUENCE)
    with pytest.raises(ValueError):
        encode(DATA, bytes(16), MAX_SEQUENCE+1)
    m = dict(filename='x', size=1 << 40, chunk=1, count=1 << 40, window=1, sha256='0'*64)
    assert receiver.metadata(json.dumps(m).encode(), 1 << 40)['count'] == 1 << 40
    m.update(size=(1 << 40)+1, count=(1 << 40)+1)
    with pytest.raises(ValueError):
        receiver.metadata(json.dumps(m).encode(), 1 << 50)


def test_actual_wire_counters():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        channel = Channel(sock, loss=1)
        assert channel.send(b'test', sock.getsockname()) is False
        assert channel.drops == 1 and channel.bytes_sent == 0
        channel.loss = 0
        assert channel.send(b'test', sock.getsockname()) is True
        assert channel.bytes_sent == 4 and channel.packets_sent == 1


def test_dashboard_transfer(tmp_path):
    source = tmp_path/'synthetic.bin'; synthetic(source, 65537)
    original = digest(source); completed = []
    with local_receiver('udp', tmp_path/'out', window_size=8, dashboard=True,
                        on_complete=completed.append) as port:
        result = sender.send(source, port=port, window_size=8, loss=.1, reorder=.2,
                             seed=7, dashboard=True)
    assert result['sha256'] and result['acknowledged_packets'] == 65
    assert result['bytes_transmitted'] > source.stat().st_size
    assert result['retransmissions'] > 0 and completed[0]['out_of_order'] > 0
    assert digest(source) == digest(tmp_path/'out'/source.name) == original
    assert not list((tmp_path/'out').glob('*.part'))


def test_dashboard_failure(tmp_path):
    path = tmp_path/'empty'; path.touch()
    with pytest.raises(TimeoutError), Dashboard(True) as display:
        display.update(force=True, total=0)
        sender.send(path, port=1, retries=0, timeout=.01, loss=1, dashboard=True)
    assert display.state['verified'] == 'Not confirmed'


def test_benchmark_exports(tmp_path):
    rows = run(tmp_path, trials=2, sizes=(2048,), windows=(4,), losses=(0,), no_plots=True)
    assert len(rows) == 6 and all(r['success'] for r in rows)
    comparison = [r for r in rows if r['experiment'] == 'comparison']
    assert {r['protocol'] for r in comparison} == {'tcp', 'udp'}
    assert len({r['payload_sha256'] for r in comparison}) == 1
    assert all(r['sender_latency'] == 0 and r['loss'] == 0 for r in comparison)
    summaries = list(csv.DictReader((tmp_path/'summary.csv').open()))
    assert all(int(r['successes']) == 2 and float(r['seconds_stdev']) >= 0 for r in summaries)
    assert json.loads((tmp_path/'conditions.json').read_text())['measured'] is True
    with pytest.raises(ValueError, match='already exist'):
        run(tmp_path, no_plots=True)


def test_failure_summary():
    rows = [dict(experiment='comparison', protocol='tcp', size=1, window=0, loss=0,
                 sender_latency=0, success=False)]
    summary = summarize(rows)[0]
    assert summary['failures'] == 1 and 'seconds_mean' not in summary


def test_existing_partial_not_deleted(tmp_path):
    # An exclusive-create failure must not delete a file this session did not create.
    from bionet.protocol import START, ERROR, decode
    sid = bytes(16)
    partial = tmp_path/('.'+sid.hex()+'.part'); partial.write_bytes(b'owned elsewhere')
    m = dict(filename='new', size=0, chunk=1024, count=0, window=1, sha256='0'*64)
    with local_receiver('udp', tmp_path, quiet=True) as port:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1)
            sock.sendto(encode(START, sid, payload=json.dumps(m).encode()), ('127.0.0.1', port))
            assert decode(sock.recv(2048))[0] == ERROR
    assert partial.read_bytes() == b'owned elsewhere'
