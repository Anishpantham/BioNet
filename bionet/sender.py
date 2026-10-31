import json
import socket
import time
import uuid
from pathlib import Path
from .protocol import *
from .integrity import digest
from .impairment import Channel

def send(file, host='127.0.0.1', port=9000, window_size=32, chunk_size=1024, timeout=.1, retries=50, verbose=False, **impairment):
    if not 1 <= window_size <= 4096 or not 1 <= chunk_size <= 1024 or timeout <= 0 or retries < 0:
        raise ValueError('invalid sender limits')
    path = Path(file); size = path.stat().st_size; sid = uuid.uuid4().bytes
    count = (size + chunk_size - 1) // chunk_size
    meta = dict(filename=path.name, size=size, chunk=chunk_size, count=count, window=window_size, sha256=digest(path))
    peer = (socket.gethostbyname(host), port); retransmissions = 0
    started = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(.005); channel = Channel(sock, **impairment)
        def poll():
            channel.flush()
            try:
                raw, address = sock.recvfrom(2048)
                kind, session, seq, payload = decode(raw)
                if address != peer or session != sid:
                    return None
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
        negotiated = int(control(START, START_ACK, json.dumps(meta).encode()))
        if not 1 <= negotiated <= window_size:
            raise ValueError('invalid negotiated window')
        base = next_seq = 0; pending = {}; acked = set()
        with path.open('rb') as stream:
            while base < count:
                while next_seq < min(count, base + negotiated):
                    packet = encode(DATA, sid, next_seq, stream.read(chunk_size))
                    channel.send(packet, peer); pending[next_seq] = [packet, time.monotonic(), 0]
                    next_seq += 1
                answer = poll()
                if answer and answer[0] == ACK and answer[1] in pending:
                    seq = answer[1]; del pending[seq]; acked.add(seq)
                    if verbose:
                        print(f'ACK {seq} ({seq + 1}/{count})', flush=True)
                    while base in acked:
                        acked.remove(base); base += 1
                now = time.monotonic()
                for seq, record in pending.items():
                    if now - record[1] >= timeout:
                        if record[2] >= retries:
                            raise TimeoutError(f'DATA {seq} retry exhaustion')
                        channel.send(record[0], peer); record[1] = now; record[2] += 1; retransmissions += 1
                        if verbose:
                            print(f'retransmit DATA {seq}', flush=True)
        control(FIN, FIN_ACK)
        elapsed = time.monotonic() - started
        return dict(session=sid.hex(), filename=path.name, size=size, seconds=elapsed, goodput_mbps=size * 8 / elapsed / 1e6, packets_transmitted=channel.sent-channel.drops, retransmissions=retransmissions, simulated_drops=channel.drops, success=True, sha256=True)
