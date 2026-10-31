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
Benchmarks create actual CSV, four PNG graphs, and use only temporary synthetic
payloads. TCP is a functional baseline; automated comparative TCP sweeps remain
pending. No claim of superiority over TCP is made.

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
