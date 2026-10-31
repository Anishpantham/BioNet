"""Single active session, bounded reorder buffer, atomic no-clobber publish."""
import hashlib
import json
import os
from pathlib import Path
import socket
import time
from .protocol import *
from .dashboard import Dashboard
from .impairment import Channel

def metadata(payload, max_size):
    m = json.loads(payload)
    if not isinstance(m, dict):
        raise ValueError('metadata object required')
    name = m['filename']
    if not isinstance(name, str) or not name or len(name.encode()) > 200 or name in ('.', '..') or '/' in name or '\\' in name or '\x00' in name:
        raise ValueError('unsafe filename')
    for key in ('size', 'chunk', 'count', 'window'):
        if type(m[key]) is not int:
            raise ValueError('integer required')
    if not 0 <= m['size'] <= min(max_size, MAX_FILE_SIZE) or not 1 <= m['chunk'] <= 1024 or not 1 <= m['window'] <= 4096:
        raise ValueError('resource limit')
    if not 0 <= m['count'] <= MAX_SEQUENCE or m['count'] != (m['size'] + m['chunk'] - 1) // m['chunk']:
        raise ValueError('packet count')
    if not isinstance(m['sha256'], str) or len(m['sha256']) != 64 or any(c not in '0123456789abcdef' for c in m['sha256']):
        raise ValueError('digest')
    return m

def receive(host='127.0.0.1', port=9000, output='received', window_size=32, idle_timeout=30, max_size=1 << 40, stop=None, ready=None, dashboard=False, on_complete=None, quiet=False, **impairment):
    if not 1 <= window_size <= 4096 or idle_timeout <= 0 or max_size < 0:
        raise ValueError('invalid receiver limits')
    root = Path(output); root.mkdir(parents=True, exist_ok=True)
    active = None; completed = {}; stream = None; temp = None
    with Dashboard(dashboard, role='receiver (local observations)') as display, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((host, port)); sock.settimeout(.005)
        channel = Channel(sock, **impairment)
        if ready:
            ready(sock.getsockname()[1])
        try:
            while stop is None or not stop.is_set():
                channel.flush(); now = time.monotonic()
                completed = {k: v for k, v in completed.items() if v > now}
                if active and now - last > idle_timeout:
                    stream.close(); temp.unlink(missing_ok=True); active = None
                    buffer.clear()
                    display.update(force=True, status='Idle timeout; partial file deleted', verified='Not confirmed')
                try:
                    raw, peer = sock.recvfrom(2048)
                    kind, sid, seq, payload = decode(raw)
                except (socket.timeout, ValueError):
                    continue
                key = (peer, sid)
                def reply(k, data=b''):
                    channel.send(encode(k, sid, seq, data), peer)
                if key in completed:
                    if kind == FIN:
                        reply(FIN_ACK)
                    continue
                if kind == START:
                    if active == key:
                        received += len(raw)
                        reply(START_ACK, str(min(window_size, m['window'])).encode()); continue
                    if active or len(completed) >= 1024:
                        reply(ERROR, b'receiver busy'); continue
                    try:
                        m = metadata(payload, max_size)
                        target = root / m['filename']
                        if target.exists():
                            raise ValueError('destination exists')
                        candidate = root / ('.' + sid.hex() + '.part')
                        stream = candidate.open('xb')
                        temp = candidate
                    except (ValueError, KeyError, TypeError, OSError):
                        reply(ERROR, b'invalid metadata or destination'); continue
                    active = key; base = 0; buffer = {}; last = now
                    hasher = hashlib.sha256(); received = len(raw); out_of_order = written = 0
                    started = sample_time = now; sample_bytes = 0
                    tx_start, drops_start = channel.bytes_sent, channel.drops
                    display.started = now
                    display.state = dict(status='Receiving', verified='Pending')
                    display.update(force=True, status='Receiving', verified='Pending', size=m['size'],
                                   total=m['count'], done=0, acked=0, base=0, cells=(),
                                   width=min(window_size, m['window']), retries='N/A')
                    reply(START_ACK, str(min(window_size, m['window'])).encode()); continue
                if key != active:
                    continue
                last = now
                received += len(raw)
                if kind == DATA:
                    expected = min(m['chunk'], m['size'] - seq * m['chunk'])
                    if seq >= m['count'] or len(payload) != expected:
                        continue
                    if seq < base:
                        reply(ACK); continue
                    if seq >= base + min(window_size, m['window']):
                        continue
                    if seq > base and seq not in buffer:
                        out_of_order += 1
                    buffer[seq] = payload; reply(ACK)
                    while base in buffer:
                        data = buffer.pop(base)
                        stream.write(data); hasher.update(data); written += len(data); base += 1
                    if dashboard and now - sample_time >= .2:
                        rate = (written-sample_bytes)*8/(now-sample_time)/1e6
                        sample_time, sample_bytes = now, written
                        display.update(status='Receiving (ACKed = accepted; reply may be lost)',
                                       done=written, acked=base+len(buffer), base=base,
                                       outstanding=len(buffer), tx=channel.bytes_sent-tx_start, rx=received,
                                       drops=channel.drops-drops_start, rate=rate, out_of_order=out_of_order,
                                       cells=tuple((n, 'A' if n in buffer else 'P') for n in range(base, min(m['count'], base+min(window_size, m['window']), base+32))))
                elif kind == FIN and base == m['count']:
                    stream.close()
                    if temp.stat().st_size != m['size'] or hasher.hexdigest() != m['sha256']:
                        temp.unlink(); active = None; reply(ERROR, b'SHA256 mismatch')
                        display.update(force=True, status='Rejected', verified='FAIL')
                        continue
                    try:
                        os.link(temp, target)
                    except OSError:
                        temp.unlink(); active = None; reply(ERROR, b'cannot publish'); continue
                    temp.unlink(); active = None; completed[key] = now + 120
                    reply(FIN_ACK)
                    result = dict(session=sid.hex(), filename=m['filename'], sha256='PASS',
                                  simulated_drops=channel.drops-drops_start, out_of_order=out_of_order,
                                  bytes_written=written)
                    display.update(force=True, status='Reconstructed and published', verified='PASS',
                                   done=written, acked=base, base=base, outstanding=0, cells=(),
                                   tx=channel.bytes_sent-tx_start, rx=received,
                                   drops=channel.drops-drops_start, out_of_order=out_of_order, elapsed=now-started)
                    if on_complete:
                        on_complete(result)
                    if not quiet and not dashboard:
                        print(json.dumps(result), flush=True)
        finally:
            if stream and not stream.closed:
                stream.close()
            if temp:
                temp.unlink(missing_ok=True)
