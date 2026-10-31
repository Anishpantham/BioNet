"""Nonblocking, seeded outbound scheduling on real UDP sockets."""
import heapq
import random
import time

class Channel:
    def __init__(self, sock, loss=0, latency=0, jitter=0, reorder=0, corruption=0, seed=1):
        if any(not 0 <= x <= 1 for x in (loss, reorder, corruption)) or min(latency, jitter) < 0:
            raise ValueError('invalid impairment')
        self.sock, self.loss, self.latency, self.jitter = sock, loss, latency, jitter
        self.reorder, self.corruption = reorder, corruption
        self.rng = random.Random(seed)
        self.queue = []
        self.sent = self.drops = self.counter = 0

    def send(self, packet, address):
        self.sent += 1
        if self.rng.random() < self.loss:
            self.drops += 1
            return
        if self.rng.random() < self.corruption:
            packet = packet[:-1] + bytes([packet[-1] ^ 1])
        delay = max(0, self.latency + self.rng.uniform(-self.jitter, self.jitter))
        if self.rng.random() < self.reorder:
            delay += .02
        self.counter += 1
        if len(self.queue) >= 65536:
            raise RuntimeError('scheduler resource limit')
        heapq.heappush(self.queue, (time.monotonic() + delay, self.counter, packet, address))
        self.flush()

    def flush(self):
        while self.queue and self.queue[0][0] <= time.monotonic():
            _, _, packet, address = heapq.heappop(self.queue)
            self.sock.sendto(packet, address)
