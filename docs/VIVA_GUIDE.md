# Viva preparation
- UDP sends independent datagrams; delivery, ordering and duplicates are not guaranteed.
  TCP supplies an ordered reliable byte stream plus congestion control.
- Stop-and-Wait has one outstanding packet. Go-Back-N retransmits the missing packet
  and subsequent outstanding packets. Selective Repeat retains independent timers
  and retransmits only unacknowledged packets, using receiver buffering.
- Window example: 0 and 2 ACKed, 1 lost. Base stays at 1; only 1 times out.
  Receiving 1 allows buffered 2 to be written. Lost ACK? Duplicate DATA gets ACKed.
- Sequence numbers identify chunks; sessions distinguish transfers. Network byte
  order is big endian, independent of CPU architecture.
- RTT is round-trip delay. Timeout below RTT creates unnecessary retransmissions;
  too large causes long loss stalls. This implementation uses a fixed timeout.
- Goodput counts useful file bytes per second; throughput can include headers,
  retransmissions and ACKs. Mbps divides bits/second by one million.
- CRC32 detects accidental packet damage cheaply. SHA256 compares complete file
  bytes. Neither authenticates a sender; an attacker can replace metadata and data.
- `sendto`/`recvfrom` preserve UDP datagram boundaries. TCP `recv` may return fewer
  bytes than requested, requiring a read loop. UDP truncation is rejected by length.
- Why temporary files? Failed transfers never appear as verified output. Hard-link
  publication is atomic and fails if destination exists; temp and output share a filesystem.
- Why not unlimited buffering? A missing low sequence could otherwise exhaust RAM.
- Does a FIN_ACK timeout prove failure at receiver? No. The final reply can be lost
  after publication. Retries and cache reduce ambiguity but cannot eliminate it.
- Is UDP always faster? No. TCP is highly optimized; this protocol lacks congestion
  control and adaptive RTT. Localhost experiments do not predict WAN performance.
- Can this run safely on the Internet? No authentication or encryption; use a trusted LAN.
- Debug no ACKs: check IP, port, binding, firewall, CRC, session and receive window.
- Corrupt ZIP but valid CRC? File SHA256 detects aggregate corruption or modification.
- What if sender file changes during transfer? Receiver rejects final digest; keep input stable.
- What survives restart? Finalized files; active state and ACK cache do not persist.
- Why ACK out-of-order chunks? It prevents unnecessary retransmission while earlier holes recover.
- How reproducible are seeds? Random decisions are seeded, but OS scheduling can change
  retry order. Repeat trials and report measured variation instead of identical-time claims.
