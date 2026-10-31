# BioNet
Reliable binary file transmission using Selective Repeat ARQ over real UDP sockets.
Python 3.12+, macOS (including Apple Silicon) or Linux. Instructor approval of the
selected mechanism remains required. Part A biometric capture is already complete.

## Install and test
```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python scripts/generate_test_data.py
```
Two terminals, from the repository root:
```sh
python -m bionet receiver --host 0.0.0.0 --port 9000 --output received
python -m bionet sender --host 127.0.0.1 --port 9000 --file data/synthetic.zip --window-size 32 --loss .05 --verbose
```
On a LAN replace the sender host with the receiver's private IPv4 address. Allow
UDP 9000 through the host firewall. Default binding is loopback; all-interface
binding must be explicit. Each destination filename must be unused.

Sender JSON reports session, filename, size, seconds, Mbps, retransmissions,
simulated drops and verified success. Example fields (illustrative, not measurements):
`"success": true, "sha256": true`. Verbose output shows individual ACKs and retries.

`--loss` on sender affects outbound DATA and control packets; on receiver it affects
ACKs and control replies. Each endpoint independently accepts `--latency` and
`--jitter` in seconds, `--reorder`, `--corruption` and `--seed`. Independent timers
retransmit only missing DATA. Default payload 1024 bytes, timeout 100 ms, 50 retries.

```sh
python -m bionet benchmark --trials 3
python -m bionet tcp-receiver --port 9001 --output received-tcp
python -m bionet tcp-sender --port 9001 --file data/synthetic.zip
```
Benchmarks use only temporary synthetic payloads and produce measured CSV and graphs.
TCP comparison is automated in Phase 2; see the commands and methodology below.
No claim of superiority over TCP is made.

## Safety and troubleshooting
Never upload `25BCS126.zip` to cloud development or GitHub. `data/`, `received/`,
ZIPs and partial files are ignored. Use only synthetic files here. CRC32 and SHA-256
are integrity checks, **not authentication or encryption**. Use trusted private
machines and networks for real biometrics. Received archives are never extracted.
Filename validation and no-clobber atomic publication protect output paths; use a
private output directory. Incomplete and failed files are deleted.

Retry exhaustion: check host, firewall, receiver logs, and increase timeout for
high latency. Destination exists: select another output directory or explicitly
move your prior output. Receiver handles one active session; concurrent senders
receive an error. Interrupted sessions expire after `--idle-timeout` seconds.
Completed-session replies are cached 120 seconds (maximum 1024); completion cannot
be guaranteed under unlimited loss or after a receiver restart. A sender may
report timeout even though the receiver safely finalized a file.

See docs for wire format, architecture, experiments, three-minute demo, viva,
and the two-page report draft. Environment setup uses the existing isolated
checkout; no additional worktree is needed.

## Phase 2: dashboard and evaluation

```sh
python -m pip install -e '.[dev,dashboard]'
# Terminal 1 (choose an unused destination directory):
python -m bionet receiver --output received-demo --dashboard
# Terminal 2:
python -m bionet sender --file data/synthetic.zip --window-size 8 --loss .1 --reorder .3 --dashboard
# Guided synthetic-only demonstration (~3 minutes with presenter pauses):
python -m scripts.demo --output results/demo-session
# Repeated experiments; choose a fresh output directory for each run:
python -m bionet benchmark --output results/evaluation --trials 3 --sizes 65536 262144 --windows 8 32 --losses 0 .05 .1 .2
# Plot existing measurements again:
python -m scripts.plot_results --output results/evaluation
```

Without `--dashboard`, no Rich import or live rendering occurs. Install only
`.[dashboard]` for monitoring, or `.[dev]` for pytest and graph generation.
The dashboard writes to stderr; sender JSON remains on stdout. `--verbose` is
suppressed when the dashboard is active. It shows progress, payload goodput,
local TX/RX BioNet bytes, total/ACKed DATA, window base, outstanding packets,
retries, simulated drops, elapsed time and final verification. Green A = ACKed,
yellow P = pending, red L = simulated outbound drop, magenta R = retransmitted.
Only the first 32 slots of the current window are drawn; counters cover all slots.
No payload, filename or digest is rendered in the dashboard.

Sender progress counts uniquely ACKed payload bytes; receiver progress counts
contiguous bytes written. Receiver ACKed means accepted locally, outstanding
means buffered out-of-order packets, and base is its receive window. It cannot
know the sender's retry count or exact window; these are not fabricated.
A red L is a simulator observation, not inferred network loss. Rates are sampled
payload goodput, not physical-link throughput. UI snapshots are capped at 5 Hz;
use dashboards off for timing experiments. See [methodology](docs/EXPERIMENTS.md).

Benchmarks now run standard TCP and Selective Repeat UDP on identical synthetic
payloads without artificial impairment for the comparison. A separate UDP sweep
uses 2 ms sender delay and configurable loss. Outputs include raw CSV, summary
CSV, conditions JSON and five PNGs. `--no-plots` permits collection without
Matplotlib. Existing output CSVs are never overwritten. Default output is now
`results/phase2`, protecting the original Phase 1 results.

See [review](docs/PHASE2_REVIEW.md), [demo guide](docs/DEMO_GUIDE.md),
[submission checklist](docs/SUBMISSION_CHECKLIST.md) and [Phase 2 validation](docs/PHASE2_VALIDATION.md).
