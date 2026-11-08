# Final Biometric Transfer Validation

## Environment

- Platform: MacBook Air M4, macOS
- Python: 3.12
- Transport: Real UDP sockets over localhost (127.0.0.1)
- Protocol: BioNet Selective Repeat ARQ
- Sender window: 32
- Simulated sender-side packet loss: 5%
- Dataset: Private biometric ZIP, not included in repository

## Actual Biometric Transfer Results

| Metric | Result |
|---|---|
| File size | 2,774,235,808 bytes |
| Completion time | 6,453.9000925 seconds |
| Final sender-reported goodput | 3.438833 Mbps |
| DATA packets acknowledged | 2,709,215 / 2,709,215 |
| Retransmissions | 143,000 |
| Simulated outbound drops | 143,000 |
| Receiver out-of-order arrivals | 1,857,096 |
| Sender SHA-256 | PASS |
| Receiver SHA-256 | PASS |
| Independent byte comparison | PASS |

## Independent Verification

The original private biometric ZIP and reconstructed ZIP were
compared using the macOS `cmp` utility.

Result:

    BYTE-FOR-BYTE VERIFICATION: PASS

This establishes exact byte-for-byte reconstruction.

## Automated Testing

- macOS pytest: 181 passed in 30.79 seconds
- macOS synthetic validation: passed
- Synthetic ZIP transfer: SHA-256 PASS

## Limitations

The actual biometric transfer used localhost, not two separate
physical devices. Packet loss was simulated at the sender, not
measured on a physical network.

BioNet does not provide encryption or sender authentication.

The actual biometric dataset and reconstructed copy must remain
private and must never be committed to this repository.

Instructor approval of the selected protocol and any required
two-device LAN demonstration must be confirmed separately.
