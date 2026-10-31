# Architecture
```mermaid
flowchart LR
 File[Binary file] --> Hash[Streaming SHA256 and segmentation]
 Hash --> Sender[Selective Repeat sender window]
 Sender --> Scheduler[Seeded heap scheduler]
 Scheduler --> UDP[Real UDP socket]
 UDP --> Receiver[CRC and session validation]
 Receiver --> Buffer[Bounded reorder buffer]
 Buffer --> Temp[Sequential temporary file]
 Temp --> Verify[Size and SHA256]
 Verify --> Output[Atomic no-clobber output]
 Receiver --> ACK[Individual ACK]
 ACK --> Sender
```
Modules separate wire codec, hashing, channel scheduling, sender, receiver,
TCP baseline, CLI and benchmarks. Sender memory O(window × chunk); receiver
memory O(window × chunk). Hashing uses 1 MiB streaming reads. Scheduled datagrams
have a hard queue cap. Receiver cache has a fixed cap and expiration.
