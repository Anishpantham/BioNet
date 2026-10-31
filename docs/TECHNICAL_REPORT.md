# BioNet: Reliable File Transmission Using Selective Repeat ARQ over UDP
*Two-page report draft: approximately 650 words; use 10–11 pt, one small architecture
figure and one results table. Final PDF pagination remains to be checked.*

## Objective and architecture
The assignment requires transferring a captured biometric archive, reconstructing
its bytes and evaluating a genuine networking mechanism. Selective Repeat ARQ is
the proposed mechanism, subject to instructor approval. Development and all cloud
measurements use synthetic data; the actual biometric LAN demonstration is pending.

Architecture: file → streaming SHA-256 → segmentation → sender window → UDP →
receiver reorder buffer → contiguous temporary output + SHA-256 → atomic publication.
Individual ACKs return to the sender. The full renderable architecture and message
sequence diagrams are in ARCHITECTURE.md and PROTOCOL.md.

## Protocol and implementation
Python 3.12 sockets carry the existing BioNet v1 format: 32-byte network-order
header (magic, version, packet type, UUID session, unsigned 64-bit sequence, payload
length), payload and 4-byte CRC32. Default DATA payload is 1024 bytes. START conveys
size, filename, chunk count, window and expected SHA-256; START_ACK negotiates the
minimum endpoint window. FIN_ACK confirms size/hash validation and publication.

Each pending DATA packet has its own timestamp and retry budget. Later ACKs do
not move the left edge past a hole. For example, ACKs 0,2,3 leave base at 1;
only unacknowledged 1 is retried. The receiver buffers later chunks and writes them
in sequence once the hole closes. Duplicate DATA is ACKed without duplicate writes.
Control retries and a bounded 120-second completion cache tolerate lost replies.

File contents are streamed. Sender/receiver buffers scale with window × chunk;
window ≤4096 and file size ≤1 TiB. Even one-byte chunks fit the sequence space.
The UDP receiver hashes contiguous output while writing, avoiding another full-file
read before FIN_ACK. Temporary files are removed on handled failure, idle timeout
or graceful receiver shutdown. Source files are read-only; publication cannot
silently replace an existing destination. Forced termination can leave partials.

The optional Rich dashboard shows progress, local bytes, ACKs, base/window, outstanding
packets, retries, simulated drops, sampled goodput, elapsed time and verification.
It receives only counters and up to 32 colored slots, refreshed at most five times
per second. It displays no file contents and is disabled for benchmarks.

## Experimental method and evidence
The framework generates identical synthetic payloads for standard TCP and custom
UDP on loopback. Comparison rows have no artificial impairment; protocol order
alternates across trials. Separate UDP sweeps vary loss/window with 2 ms sender
delay and independent seeded loss at both endpoints. Both timers exclude initial
source hashing and receiver startup, and include verified completion. TCP still
rereads output for hashing; UDP hashes while writing, an implementation difference.

Goodput = useful payload bits / completion seconds. Application overhead counts
sender-observed socket bytes minus useful payload; it excludes kernel TCP ACKs,
retries and transport/link headers. CSV retains failures; summaries report sample
count, successes/failures, mean, sample SD and range. Five plots show loss/window
trends and TCP comparison. Conditions record platform, Python and settings.

Historical Phase 1 evidence comprises 48 synthetic localhost transfers, 64/256 KiB,
windows 8/32 and three trials per configuration; all passed SHA-256:

|Configured loss per direction|Mean goodput (Mbps)|Mean completion (s)|
|---|---:|---:|
|0%|18.777|0.0826|
|5%|1.611|0.8817|
|10%|1.007|1.5501|
|20%|0.555|2.6038|

These historical aggregates mix sizes/windows and are not a TCP comparison.
Phase 2 smoke evidence is separately identified in PHASE2_VALIDATION.md; full
final evaluation is deferred. No real biometric transfer result is claimed.

## Conclusion and limitations
Selective retransmission plus receiver buffering supports reliable reconstruction
under simulated loss. CRC32 detects packet damage; SHA-256 verifies aggregate bytes.
Neither provides authentication or encryption. Fixed timeouts, finite retry/cache
budgets, no congestion control and no crash-resume limit deployment. Localhost
results do not establish LAN/WAN performance or UDP superiority. Remaining work is
final testing, controlled repeated evaluation, trusted local biometric demonstration,
instructor approval, and two-page typesetting.
