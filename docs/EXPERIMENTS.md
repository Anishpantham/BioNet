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
experiments do not establish large-ZIP WAN performance. TCP functional integration
is tested; automated TCP comparison measurements and real LAN biometric measurements
remain pending. Run both protocols on identical stable files and hosts without UDP-only
impairment when comparing baseline performance.
