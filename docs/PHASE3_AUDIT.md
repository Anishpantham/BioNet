# Phase 3 protocol and implementation audit

Audited merged `main` commit `31cd398840f830df963da91fb3808108f1f8cc8a`
(PRs #1 and #2), on `feature/phase3-stabilization`. All package modules,
existing tests, experiment/demo/generation scripts, protocol/architecture and
Phase 2 validation documents were read. The local checkout was still Phase 1;
the GitHub connector supplied main's blobs, trees and signed commit. Git object
hashes were verified before switching. No project rebuild or wire version change.
No biometric dataset was accessed.

## Selective Repeat

The sender's `pending` map stores each unacknowledged packet, last-send timestamp
and retry count. `acked` holds later ACKs until the contiguous left edge advances.
Sending is limited by `base + negotiated_window`, not the number of unacknowledged
packets. The receiver individually ACKs accepted DATA, buffers only its window and
drains chunks in order into the file/hash. Earlier duplicates are re-ACKed.

`test_only_missing_packet_retransmits` drops DATA 1 or ACK 1, injects duplicate,
wrong-session and out-of-window ACKs over real UDP, and proves DATA 1 is sent twice
while all other DATA is sent once. Sequence 5 waits for the hole at 1 with width 4.
`test_independent_timers` loses 0 and 2 independently and verifies only they retry.
This is packet-level evidence of Selective Repeat.

| Property | Evidence |
|---|---|
| Window negotiation/advancement | Widths 1, 2, 8, 32, 64, 128; sender 128/receiver 2; stalled-base trace |
| Individual ACKs/timers | Selective loss and independent expiry traces; duplicate ACK injection |
| DATA/ACK loss | Separate/both directions at 0, 5, 10, 20, 30, 40%; exact lost-ACK case |
| Reordering/duplicates | Delayed real traffic, explicit out-of-order/duplicate DATA and ACKs |
| Completion | Early FIN ignored; only contiguous count permits FIN; empty and partial final chunks |
| Controls | Individually lost START, START_ACK, FIN, FIN_ACK; duplicate FIN re-ACKed |
| Malformed controls | Nonzero START/FIN/FIN_ACK and nonempty FIN_ACK rejected; conflicting START errors |
| Isolation | Same SID/wrong source and wrong SID/right source ignored; concurrent START rejected |
| Restart | Active state discarded on restart; stale DATA/FIN ignored; no resume claim |
| Bounds | Window <=4096, chunk <=1024, metadata <=1200, file <=1 TiB, unsigned 64-bit sequence |
| Cache | 1024 completion cap and 120-second expiry tested with controlled receiver clock |
| Interruptions | Actual sender/receiver SIGINT, idle expiry, retry exhaustion, cleanup |

The 1 TiB cap is metadata-tested, not a 1 TiB transfer. Invalid DATA no longer
refreshes idle expiry. Duplicate valid START refreshes expiry without resetting
progress. Retry horizon plus delays must fit the 120-second completion retention;
matching endpoint timeout settings remains the operator's responsibility. A file
can be finalized even when every FIN_ACK is lost.

## Codec and file safety

V1 remains a 32-byte `!4sBB16sQH` header, <=1200 payload bytes and 4-byte CRC32.
Tests use valid CRCs with invalid header fields, truncation/oversize, a bit flip at
every byte of a maximum-payload datagram, sequence limits, unsafe names, invalid
numeric types, wrong hashes and malformed JSON. Metadata now enforces its transport
size cap at the shared API too. RecursionError is normalized defensively; no parser
crash was reproduced in this Python runtime.

Source hashes read 1 MiB blocks; source contents must remain stable. Shortening
fails and other mutations are detected by receiver SHA-256. UDP hashes contiguous
written chunks. TCP uses bounded exact reads and rereads output for SHA-256. Both
use exclusive temp creation and atomic no-clobber hard-link publication. Tests
cover existing targets/symlinks, targets created after START and pre-existing temp
ownership. ZIPs are transferred byte-for-byte and never extracted.

Injected write, flush and publication errors exercise ordinary error paths. They
are not physical disk-full, failing-device, power-loss or durability validation.
No fsync/crash recovery is promised. Use a private output directory; hostile local
processes replacing temp paths are out of scope. Unlink failure or loss of access
to the output directory can still stop the receiver.

## Impairment

Seeded outbound decisions feed a monotonic heap. `send`/`flush` use real UDP and
never sleep to inject delays. Loss precedes scheduling, corruption flips a CRC
byte, jitter varies due time and reorder adds 20 ms. Actual send counters increment
at `sendto`, excluding queued/dropped packets. The queue caps at 65,536 datagrams.
Non-finite delays are rejected. Tests observe delay, damaged CRC, queue limits,
loss counters and deterministic RNG decisions independently.

Duplication is test-injected through real sockets, not a new simulator option.
Scheduling can alter retransmission/random-call order despite identical seeds.
Retransmissions with zero simulated drops may arise from OS queues or timeout
scheduling; they are not labeled simulated loss or proven physical loss. Receiver
completion counters are a first-publication snapshot, excluding later FIN retries.

## TCP, monitoring and measurements

TCP frames metadata with a 4-byte length, then declared file bytes, then PASS/FAIL.
Real localhost tests fragment sends to individual bytes, disconnect mid-file and
check malformed-frame recovery. Inactivity timeouts are 10 s receiver/30 s sender;
they do not bound a continuously active slow client globally.

Rich is optional; state contains counts and at most 32 slots, never payload or
filename. Empty/failed/no-color and lossy normal transfers are exercised. Sender
progress is uniquely ACKed bytes; receiver progress is contiguous written bytes.
PASS requires verified completion. Terminal/device failures are not guaranteed
recoverable. Redirected-stderr overhead measurements do not certify real Terminal
rendering performance. Missing Rich produces an installation diagnostic.

Benchmarks use identical synthetic data, alternating transport order, three trials,
independent hashes, raw configurations/seeds and failure-aware summaries. Plots now
label failure omissions. Failure elapsed time includes receiver teardown and stays
separate from successful sender timing (which excludes source hash/startup). Failure
packet counters and TCP kernel packet/retransmission counts are unavailable, not
invented zeros. UDP sweeps are not equal-impaired-network TCP comparisons.

## Platform and assumptions

Standard Python 3.12, IPv4 sockets, TCP SO_REUSEADDR, threads and same-filesystem
hard links are used. No Linux-only runtime dependency or multiprocessing assumption
was found. Darwin/arm64/APFS, macOS Terminal, firewall prompts and LAN operation are
unexecuted here; the local validation script refuses to certify non-macOS hosts.

No encryption, authentication, congestion control, adaptive RTO, IPv6, resume,
concurrent active UDP sessions, Internet hardening or crash durability is claimed.
CRC32/SHA-256 provide integrity, not biometric privacy.
