"""Single active session, bounded reorder buffer, atomic no-clobber publish."""
import json
import os
from pathlib import Path
import socket
import time
from .protocol import *
from .integrity import digest
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
    if not 0 <= m['size'] <= max_size or not 1 <= m['chunk'] <= 1024 or not 1 <= m['window'] <= 4096:
        raise ValueError('resource limit')
    if m['count'] != (m['size'] + m['chunk'] - 1) // m['chunk']:
        raise ValueError('packet count')
    if not isinstance(m['sha256'], str) or len(m['sha256']) != 64 or any(c not in '0123456789abcdef' for c in m['sha256']):
        raise ValueError('digest')
    return m

def receive(host='127.0.0.1', port=9000, output='received', window_size=32, idle_timeout=30, max_size=1 << 40, stop=None, ready=None, **impairment):
    if not 1 <= window_size <= 4096 or idle_timeout <= 0:
        raise ValueError('invalid receiver limits')
    root = Path(output); root.mkdir(parents=True, exist_ok=True)
    active = None; completed = {}; stream = None; temp = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
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
                        reply(START_ACK, str(min(window_size, m['window'])).encode()); continue
                    if active or len(completed) >= 1024:
                        reply(ERROR, b'receiver busy'); continue
                    try:
                        m = metadata(payload, max_size)
                        target = root / m['filename']
                        if target.exists():
                            raise ValueError('destination exists')
                        temp = root / ('.' + sid.hex() + '.part')
                        stream = temp.open('xb')
                    except (ValueError, KeyError, TypeError, OSError):
                        reply(ERROR, b'invalid metadata or destination'); continue
                    active = key; base = 0; buffer = {}; last = now
                    reply(START_ACK, str(min(window_size, m['window'])).encode()); continue
                if key != active:
                    continue
                last = now
                if kind == DATA:
                    expected = min(m['chunk'], m['size'] - seq * m['chunk'])
                    if seq >= m['count'] or len(payload) != expected:
                        continue
                    if seq < base:
                        reply(ACK); continue
                    if seq >= base + min(window_size, m['window']):
                        continue
                    buffer[seq] = payload; reply(ACK)
                    while base in buffer:
                        stream.write(buffer.pop(base)); base += 1
                elif kind == FIN and base == m['count']:
                    stream.close()
                    if temp.stat().st_size != m['size'] or digest(temp) != m['sha256']:
                        temp.unlink(); active = None; reply(ERROR, b'SHA256 mismatch'); continue
                    try:
                        os.link(temp, target)
                    except OSError:
                        temp.unlink(); active = None; reply(ERROR, b'cannot publish'); continue
                    temp.unlink(); active = None; completed[key] = now + 120
                    reply(FIN_ACK)
                    print(json.dumps({'session': sid.hex(), 'filename': m['filename'], 'sha256': 'PASS', 'simulated_drops': channel.drops}), flush=True)
        finally:
            if stream and not stream.closed:
                stream.close()
            if temp:
                temp.unlink(missing_ok=True)
