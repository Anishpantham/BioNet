import json
import socket
import time
import uuid
from pathlib import Path
from .protocol import *
from .integrity import digest
from .impairment import Channel
from .dashboard import Dashboard

def send(file, host='127.0.0.1', port=9000, window_size=32, chunk_size=1024, timeout=.1, retries=50, verbose=False, dashboard=False, **impairment):
    if not 1 <= window_size <= 4096 or not 1 <= chunk_size <= 1024 or timeout <= 0 or retries < 0:
        raise ValueError('invalid sender limits')
    path = Path(file); size = path.stat().st_size; sid = uuid.uuid4().bytes
    count = (size + chunk_size - 1) // chunk_size
    if size > MAX_FILE_SIZE or count > MAX_SEQUENCE:
        raise ValueError('file exceeds supported 1 TiB / sequence limits')
    meta = dict(filename=path.name, size=size, chunk=chunk_size, count=count, window=window_size, sha256=digest(path))
    peer = (socket.gethostbyname(host), port); retransmissions = 0
    started = time.monotonic()
    with Dashboard(dashboard) as display, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(.005); channel = Channel(sock, **impairment)
        received_bytes = acknowledged = done = 0
        last_done = 0; last_sample = started; rate = 0.0
        states = {}
        def poll():
            nonlocal received_bytes
            channel.flush()
            try:
                raw, address = sock.recvfrom(2048)
                kind, session, seq, payload = decode(raw)
                if address != peer or session != sid:
                    return None
                received_bytes += len(raw)
                if kind == ERROR:
                    raise RuntimeError(payload.decode(errors='replace'))
                return kind, seq, payload
            except (socket.timeout, ValueError):
                return None
        def control(kind, expected, payload=b''):
            nonlocal retransmissions
            for attempt in range(retries + 1):
                channel.send(encode(kind, sid, 0, payload), peer)
                retransmissions += int(attempt > 0)
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    answer = poll()
                    if answer and answer[0] == expected:
                        return answer[2]
            raise TimeoutError('control retry exhaustion')
        display.update(force=True, status='START negotiation', size=size, total=count)
        negotiated = int(control(START, START_ACK, json.dumps(meta).encode()))
        if not 1 <= negotiated <= window_size:
            raise ValueError('invalid negotiated window')
        display.update(force=True, width=negotiated, retries=0)
        base = next_seq = 0; pending = {}; acked = set()
        with path.open('rb') as stream:
            while base < count:
                while next_seq < min(count, base + negotiated):
                    chunk = stream.read(min(chunk_size, size-next_seq*chunk_size))
                    if len(chunk) != min(chunk_size, size-next_seq*chunk_size):
                        raise OSError('source shortened during transfer')
                    packet = encode(DATA, sid, next_seq, chunk)
                    accepted = channel.send(packet, peer)
                    states[next_seq] = 'P' if accepted else 'L'
                    pending[next_seq] = [packet, time.monotonic(), 0]
                    next_seq += 1
                answer = poll()
                if answer and answer[0] == ACK and answer[1] in pending:
                    seq = answer[1]
                    done += len(pending[seq][0]) - HEADER.size - 4
                    acknowledged += 1
                    del pending[seq]; acked.add(seq); states[seq] = 'A'
                    if verbose and not dashboard:
                        print(f'ACK {seq} ({seq + 1}/{count})', flush=True)
                    while base in acked:
                        acked.remove(base); states.pop(base, None); base += 1
                now = time.monotonic()
                for seq, record in pending.items():
                    if now - record[1] >= timeout:
                        if record[2] >= retries:
                            raise TimeoutError(f'DATA {seq} retry exhaustion')
                        accepted = channel.send(record[0], peer)
                        states[seq] = 'R' if accepted else 'L'
                        record[1] = now; record[2] += 1; retransmissions += 1
                        if verbose and not dashboard:
                            print(f'retransmit DATA {seq}', flush=True)
                if dashboard and now - last_sample >= .2:
                    rate = (done-last_done)*8/(now-last_sample)/1e6
                    last_done, last_sample = done, now
                    display.update(status='Transferring', done=done, acked=acknowledged,
                                   base=base, width=negotiated, outstanding=len(pending),
                                   tx=channel.bytes_sent, rx=received_bytes, drops=channel.drops,
                                   retries=retransmissions, rate=rate,
                                   cells=tuple((n, states.get(n, '.')) for n in range(base, min(count, base+negotiated, base+32))))
        display.update(force=True, status='Receiver verifying SHA-256', done=done)
        control(FIN, FIN_ACK)
        elapsed = time.monotonic() - started
        display.update(force=True, status='Complete', verified='PASS', done=size, acked=count,
                       base=count, outstanding=0, cells=(), retries=retransmissions,
                       tx=channel.bytes_sent, rx=received_bytes, drops=channel.drops, elapsed=elapsed)
        return dict(bytes_transmitted=channel.bytes_sent, bytes_received=received_bytes,
                    application_overhead_bytes=channel.bytes_sent+received_bytes-size, total_packets=count,
                    acknowledged_packets=acknowledged, session=sid.hex(), filename=path.name, size=size, seconds=elapsed, goodput_mbps=size * 8 / elapsed / 1e6, packets_transmitted=channel.packets_sent, retransmissions=retransmissions, simulated_drops=channel.drops, success=True, sha256=True)
