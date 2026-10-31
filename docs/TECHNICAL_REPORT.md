# BioNet: Reliable Biometric Data Transmission Using Selective Repeat ARQ over UDP
*Two-page technical report draft; target 10–11 pt, two pages including diagrams.*

## Objective and architecture
Part A captured biometric data; Part B demonstrates a networking mechanism that
reconstructs an arbitrary binary archive despite packet loss. The selected
Selective Repeat ARQ mechanism remains subject to instructor approval. Cloud work
uses exclusively synthetic files; the actual 25BCS126.zip remains local.

The pipeline is file → streaming SHA256 → segmentation → sender window → UDP →
receiver reorder buffer → temporary file → size/hash verification → atomic output.
Individual ACKs return through UDP. See ARCHITECTURE.md and PROTOCOL.md for the
renderable architecture and packet exchange diagrams.

## Protocol and implementation
Python 3.12 standard-library sockets carry a custom versioned binary protocol.
The 32-byte network-order header includes magic, version, type, UUID session,
64-bit sequence and 16-bit payload length; a four-byte CRC32 protects header and
payload. Default DATA payload is 1024 bytes. START metadata contains filename,
size, packet count, chunk size, proposed window and expected SHA256. START_ACK
negotiates the minimum endpoint window. FIN_ACK confirms verified publication.

The sender tracks each outstanding packet with an independent timestamp and retry
count. Acknowledged later packets remain logically ahead of the left window edge
until holes close. The receiver buffers valid out-of-order packets only within
its bounded window and writes contiguous chunks. Duplicate DATA is acknowledged
without duplicate writes. START and FIN use bounded retries; completed sessions
retain replies for 120 seconds. Memory is proportional to window size, not file size.

A seeded heap scheduler injects loss, delay, jitter, corruption and reordering
without sleeping the protocol loop. Packets still traverse actual UDP sockets.
The TCP baseline uses framed metadata, streaming reads and verified completion.
Output filenames are validated; failed partial files are deleted; existing files
are never silently replaced. CRC32 catches packet damage, while streaming SHA256
checks end-to-end equality. Neither provides encryption or authentication.

## Experimental setup and actual results
48 localhost transfers used 64 KiB and 256 KiB synthetic files, windows 8 and 32,
three trials each, and 0%, 5%, 10%, 20% independently configured loss in both
directions. Sender artificial delay was 2 ms; timeout 100 ms. Every transfer
passed receiver SHA256 verification. Measured averages across sizes/windows:

|Loss|Goodput (Mbps)|Completion (s)|Retransmissions total|
|---|---:|---:|---:|
|0%|18.777|0.0826|0|
|5%|1.611|0.8817|194|
|10%|1.007|1.5501|496|
|20%|0.555|2.6038|1076|

Goodput counts successful application bits divided by completion time. Completion
includes control exchange and verification but excludes initial sender hashing.
CSV data and four plots are included. Sender packet/drop counters and receiver
drop logs explicitly distinguish simulated loss. Unit and actual-socket tests
exercise serialization, CRC rejection, binary/empty transfers, loss, duplicates,
reordering, control loss, retry exhaustion, resource limits, cleanup and TCP.

## Conclusion and limitations
Selective retransmission recovers missing packets while retaining later arrivals;
measured loss increases retries and completion time. Integrity checks prevent false
verified output. This educational protocol lacks authentication, encryption,
congestion control, adaptive timeouts and crash-resume. Finite completion caching
cannot eliminate uncertainty after long outages. Localhost results do not predict
LAN/WAN performance or prove superiority over TCP. Remaining submission work:
instructor approval, real biometric transfer on a trusted local LAN, TCP comparative
measurements, final two-page typesetting, and individual viva preparation.
