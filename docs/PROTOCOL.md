# Protocol version 1
All integers are unsigned network byte order (`!4sBB16sQH`).

| Offset | Bytes | Meaning |
|---|---:|---|
|0|4|ASCII BNET|
|4|1|Version 1|
|5|1|Type: START=1, START_ACK=2, DATA=3, ACK=4, FIN=5, FIN_ACK=6, ERROR=7|
|6|16|Random UUID session|
|22|8|Sequence number|
|30|2|Payload length|
|32|N|Payload (maximum 1200 bytes)|
|32+N|4|CRC32 of header plus payload|

Default DATA datagram: 1060 bytes, plus UDP/IP headers, below Ethernet MTU.
START carries UTF-8 JSON filename, size, count, chunk, window, sha256. START_ACK
carries negotiated decimal minimum window. ACK echoes individual DATA sequence.
FIN_ACK is emitted only after size/hash checks and atomic no-clobber publication.
ERROR carries a short diagnostic. Empty files use zero DATA packets.

Sender states: HASH → START retry → WINDOW → FIN retry → DONE or FAILED.
Receiver states: IDLE → ACTIVE → VERIFY → IDLE with completed-session cache.
Invalid CRC, unrelated peers/sessions, and outside-window DATA are discarded.
Sequence numbers never wrap within a session. Buffers are bounded by window ≤4096;
chunk ≤1024. Maximum default file size is 1 TiB. Metadata length ≤1200.

Each pending packet retains its own last-send time and retry count. ACKed later
packets do not advance the left edge until all preceding packets are acknowledged.
Example: window [0,1,2,3], ACKs 0,2,3 → base 1; resend only 1. Receiver buffers
2 and 3, then writes 1,2,3 when 1 arrives. Duplicate earlier DATA is ACKed again.

```mermaid
sequenceDiagram
 Sender->>Receiver: START metadata
 Receiver->>Sender: START_ACK window
 Sender->>Receiver: DATA 0
 Sender--xReceiver: DATA 1 lost
 Sender->>Receiver: DATA 2
 Receiver->>Sender: ACK 0, ACK 2
 Sender->>Receiver: DATA 1 (individual timeout)
 Receiver->>Sender: ACK 1
 Sender->>Receiver: FIN
 Receiver->>Receiver: size + SHA256; atomic publish
 Receiver->>Sender: FIN_ACK
```
Control messages retry on timeouts. Duplicate START resends START_ACK without
resetting progress. Duplicate FIN resends FIN_ACK for 120 seconds. Retry budgets
must fit this retention period; very long custom timeouts may cause ambiguous
completion. No crash recovery, encryption, authentication, congestion control,
IPv6, or resumable transfers. CRC is not a security primitive.

## Phase 2 compatibility and counters

The v1 packet bytes and control handshake are unchanged. Both endpoints explicitly
reject files above 1 TiB. Even with a one-byte chunk this is at most 2^40 packets,
well below the unsigned 64-bit sequence space. Encoding rejects out-of-range
sequence values before packing. Empty files still use START/FIN with no DATA.
The receiver's SHA-256 is updated in reconstructed order while writing, never in
arrival order. A FIN_ACK still means size/hash validation and publication succeeded.

Simulator `packets_sent` and `bytes_sent` increment only on actual socket sends,
excluding intentional drops and datagrams still queued. Sender received bytes
count CRC-valid replies from its peer/session (including duplicate replies).
Receiver monitoring counts accepted-session datagrams, excluding unrelated traffic;
it does not estimate unseen sender drops. Retransmissions include DATA and control
retries. TCP packet/retransmission counts are unavailable at the application layer.
