# Three-minute guided demonstration

Install `python -m pip install -e '.[dev,dashboard]'`, then from the repository root:

```sh
python -m scripts.demo --output results/demo-session
```

Use a fresh output directory. The script only generates synthetic ZIPs inside a
temporary directory; it never accepts a dataset path. Enter advances presenter
pauses. Runtime depends on the machine; the narrative fits about three minutes.
`--non-interactive` skips pauses for smoke checks; `--no-dashboard` uses ACK/retry
text if Rich is unavailable (Matplotlib is still needed for graphs).

| Time | Action and explanation |
|---|---|
|0:00–0:25|Introduce UDP and Selective Repeat: individual ACKs, bounded windows, independent timers. Generate a 256 KiB synthetic ZIP.|
|0:25–0:55|Script binds a UDP receiver to an ephemeral loopback port, reports readiness and starts the sender. Show loss-free reconstruction.|
|0:55–1:50|Second receiver/output: 10% outbound loss on each endpoint, 30% sender reorder probability, window 8. Show ACKed later slots while base waits for a hole, red simulated drops and magenta retries. Explain only outstanding packets retry.|
|1:50–2:10|Read measured retry and out-of-order arrival counts. Contiguous reconstruction drains buffered packets. Receiver verification and an independent streaming SHA-256 comparison both pass.|
|2:10–2:35|Script runs TCP/UDP on identical 64 KiB synthetic payloads, no impairment, two trials. Read completion time and goodput; show the separate loss sweep.|
|2:35–3:00|Open comparison PNG and summary CSV. Explain CRC vs SHA-256, lack of authentication/encryption, finite retries and limitations of localhost measurements.|

The UI samples states, so a fast ACK may never appear on screen. The receiver's
observed out-of-order count and sender retry count provide evidence after completion;
random simulation does not promise a particular packet trace. The guide's timings
are presenter targets, not measured transport results. Transfer evidence is saved
in `transfer_evidence.json`, with CSVs, conditions and five plots in `benchmark/`.

For two actual terminal processes instead of the scripted in-process endpoints:

```sh
python scripts/generate_test_data.py --output data/demo.zip --size 262144
python -m bionet receiver --output received-demo --window-size 8 --loss .1 --dashboard
# In the second terminal:
python -m bionet sender --file data/demo.zip --window-size 8 --loss .1 --reorder .3 --seed 7 --dashboard
```

Stop the receiver with Ctrl-C. A fresh destination prevents accidental overwrite.
The automated demo is exclusively synthetic. The assignment's eventual local
biometric LAN demonstration remains a separate, unexecuted submission step after
final testing. Keep that dataset outside Git/cloud, never display its contents,
and do not extract received archives automatically.

Team roles: student 1 sender/codec; student 2 receiver/integrity;
student 3 evaluation/demo. Each student should explain all protocol states.
