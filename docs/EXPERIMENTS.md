# Executed experiments
48 real localhost UDP transfers: sizes 65,536 and 262,144 bytes; windows 8 and 32;
loss probabilities 0, .05, .1, .2 applied independently at both endpoints;
three trials per configuration; sender delay 2 ms; timeout 100 ms; default
1024-byte DATA. All 48 reconstructed files passed SHA256.

| Loss | Mean goodput Mbps | Mean completion s | Total retransmissions (12 trials) |
|---|---:|---:|---:|
|0%|18.777|0.0826|0|
|5%|1.611|0.8817|194|
|10%|1.007|1.5501|496|
|20%|0.555|2.6038|1076|

Aggregates mix both sizes and windows; use the CSV and graph series for controlled
comparisons. Results are measurements, not theoretical estimates. Sender completion
time begins after initial hashing and includes setup, delivery and verified FIN_ACK.
Goodput = file bytes × 8 / elapsed / 1e6. CSV packet and simulated-drop counters
cover sender outbound traffic only; receiver logs separately report cumulative
reply drops. They are deliberately simulated drops, not estimates of real network loss.
Packet attempts that are dropped by the simulator are excluded from transmitted count.

Raw console output: results/experiment.log. Four graphs are generated from successful
CSV rows, not invented data. Failures remain in CSV and are excluded from plot means.
Seeds reproduce random streams, not OS scheduling. These small synthetic localhost
experiments do not establish large-ZIP WAN performance. At the end of Phase 1, TCP functional integration was tested; automated comparison
and real LAN biometric measurements were pending. Phase 2 status is below. Run both protocols on identical stable files and hosts without UDP-only
impairment when comparing baseline performance.

## Phase 2 methodology (historical results above are unchanged)

The 48-transfer table above is **Phase 1 historical evidence** from the merged
repository, not a rerun of Phase 2. Automated TCP comparison is now implemented.
Run a fresh experiment directory:

```sh
python -m bionet benchmark --output results/evaluation --trials 3 --sizes 65536 262144 --windows 8 32 --losses 0 .05 .1 .2
# Equivalent script entry point:
python -m scripts.run_experiments --output results/evaluation-another --trials 3
python -m scripts.plot_results --output results/evaluation
```

Two distinct experiment groups are recorded:

1. `comparison`: TCP once per size/trial, UDP once per size/window/trial. Same
   synthetic filename, size and byte pattern; CSV records the payload SHA-256.
   Same loopback host/process and no artificial loss, delay, jitter or reordering.
   Protocol order reverses on alternate trials to reduce systematic ordering bias.
   TCP uses the standard OS stack with 64 KiB application reads; UDP uses 1024-byte
   chunks, negotiated window, 100 ms timeout and 50 retries. These implementation
   choices are part of the comparison, not proof about transport protocols generally.
2. `udp_sweep`: selected size/window/loss combinations, independent configured
   loss at both endpoints and 2 ms sender delay. Seeds are trial index at sender,
   trial index + 100 at receiver. These curves are **not** impaired TCP comparisons.
   Equal TCP/UDP loss/delay evaluation requires external network emulation on both
   protocols and is deferred to final evaluation.

Both timers start after initial source hashing, before socket setup/control exchange,
end on verified receiver reply, and exclude receiver startup and independent post-run
hash checking. UDP hashes while writing; the existing TCP receiver hashes by rereading
its reconstructed file. This I/O difference is disclosed, and matters for larger files.
Goodput = useful payload bits / measured completion seconds / 10^6. Dashboard off.

`bytes_transmitted` is sender socket application bytes; `bytes_received` is valid
reply bytes seen by sender. `application_overhead_bytes` is their sum minus payload
size. For UDP this includes BioNet framing, control messages and repeated payloads;
for TCP it is length framing, JSON metadata and PASS. It excludes IP/UDP/TCP/link
headers, kernel TCP ACKs and TCP retransmissions. It is a partial, sender-observed
application cost, **not full wire overhead**; lost incoming replies are not counted.
TCP packet/drop/retransmission fields remain blank, not invented zeroes.

Outputs:

- `benchmark_results.csv`: measured successful and failed trial rows; each completed
  trial is persisted. `conditions.json`: timestamp, platform, Python and all settings.
- `summary.csv`: trials, successes, failures, mean, sample SD, min/max per fixed
  experiment/protocol/size/window/loss/delay configuration. Single-trial SD is blank.
- `throughput_loss.png`, `time_loss.png`, `retransmissions_loss.png`,
  `throughput_window.png`, `tcp_udp_comparison.png`: success-only means with sample
  SD bars (zero-length bars when n=1). Failures remain in CSV/summary; inspect them
  alongside the plots. An all-failure group has no numeric performance mean.

Do not pool sizes/windows to claim superiority. Repeat at least three times for
final evaluation, report failure rates and variation, and retain conditions.
Seeded random choices do not make scheduling or timing deterministic. There is
no warmup, CPU affinity, disk-cache control or real-network emulation here.
Phase 2 includes only a short measured smoke demonstration; full sweeps, large-file
memory/stress tests, controlled LAN tests and real biometric measurements remain pending.
