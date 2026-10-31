"""Single active session, bounded reorder buffer, atomic no-clobber publish."""
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import time
from .protocol import *
from .dashboard import Dashboard
from .impairment import Channel

def metadata(payload, max_size):
    if len(payload) > 1200:
        raise ValueError('metadata too large')
    try:
        m = json.loads(payload)
    except RecursionError as exc:
        raise ValueError('metadata nesting too deep') from exc
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
    if type(window_size) is not int or type(max_size) is not int or not math.isfinite(idle_timeout) or not 1 <= window_size <= 4096 or idle_timeout <= 0 or max_size < 0:
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
                    try:
                        stream.close()
                    except OSError:
                        display.update(force=True, status='Disk close failed on idle timeout', verified='FAIL')
                    finally:
                        temp.unlink(missing_ok=True); temp = None; active = None
                        buffer.clear()
                    display.update(force=True, status='Idle timeout; partial file deleted', verified='Not confirmed')
                try:
                    raw, peer = sock.recvfrom(2048)
                    kind, sid, seq, payload = decode(raw)
                except (socket.timeout, ValueError):
                    continue
                if kind in (START, FIN) and seq != 0 or kind == FIN and payload:
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
                        if payload != start_payload:
                            reply(ERROR, b'conflicting START metadata'); continue
                        last = now
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
                    active = key; start_payload = payload; base = 0; buffer = {}; last = now
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
                received += len(raw)
                try:
                    if kind == DATA:
                        expected = min(m['chunk'], m['size'] - seq * m['chunk'])
                        if seq >= m['count'] or len(payload) != expected:
                            continue
                        if seq < base:
                            last = now
                            reply(ACK); continue
                        if seq >= base + min(window_size, m['window']):
                            continue
                        last = now
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
                            temp.unlink(); temp = None; active = None; reply(ERROR, b'SHA256 mismatch')
                            display.update(force=True, status='Rejected', verified='FAIL')
                            continue
                        try:
                            os.link(temp, target)
                        except OSError:
                            temp.unlink(); temp = None; active = None; reply(ERROR, b'cannot publish')
                            display.update(force=True, status='Publication failed', verified='FAIL')
                            continue
                        temp.unlink(); temp = None; active = None; completed[key] = now + 120
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
                except OSError:
                    # A write/flush/stat/publish failure cannot confirm completion.
                    # close() may itself repeat an already-reported flush failure.
                    try:
                        if stream and not stream.closed:
                            stream.close()
                    except OSError:
                        display.update(force=True, status='Disk close failed', verified='FAIL')
                    finally:
                        if temp:
                            temp.unlink(missing_ok=True)
                            temp = None
                        active = None
                        buffer.clear()
                    reply(ERROR, b'receiver file I/O failure')
                    display.update(force=True, status='File I/O failure', verified='FAIL')
        finally:
            try:
                if stream and not stream.closed:
                    stream.close()
            finally:
                if temp:
                    temp.unlink(missing_ok=True)
