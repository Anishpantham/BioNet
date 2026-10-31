# Phase 3 executed test and measurement results

## Final suite

**181 passed, 0 failed, 0 skipped**; pytest summary and duration are
in `results/phase3/full-tests.log`, with JUnit timing in `full-tests.xml`
(28.98 seconds including suite setup/teardown).
Audited base: `31cd398840f830df963da91fb3808108f1f8cc8a`.
Environment: Linux 6.18.57 x86_64/glibc 2.41, CPython 3.12.14, pytest 9.2.0,
Rich 15.0.0, Matplotlib 3.10.8. Exact strings are in `environment.json`.

Tests include real localhost UDP/TCP, empty/1/1023/1024/1025-byte, 64 KiB, 1 MiB,
10 MiB, deterministic binary/null data and synthetic ZIPs; all requested window
sizes; independent/bidirectional loss through 40%; controls, corruption, delay,
jitter, reordering, duplicates, session isolation, cache bounds, retry exhaustion,
source truncation, atomic no-clobber publication, injected disk errors, subprocess
SIGINT, TCP framing/EOF and optional/no-color dashboards. No biometric data used.

### Development evidence retained

- Initial full run without sandbox socket access: **25 failed, 20 passed**, 91.33 s;
  socket PermissionError and receiver startup errors. This was an environment issue.
- Network-enabled original suite: **45 passed**, 20.70 s, one unrelated AnyIO plugin
  deprecation warning about pytest CallSpec2. No product warning was hidden.
- Corrected pre-fix regression baseline: **16 failed, 5 passed**, 0.39 s.
- Same regression selection after fixes: **21 passed**, 0.66 s.
- First expanded selection: **97 passed**, 6.39 s.
- Intermediate full suite: **180 passed**, 28.66 s; the final run also includes the
  repeated-START idle-refresh regression. These overlapping runs are not summed.

One early TCP regression fixture used the same source/destination folder; that
fixture error was corrected before the confirmed baseline. Nested JSON already
failed safely on this runtime, so defensive normalization is not counted as a
reproduced remote parser crash. Full development logs are retained.

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` avoids unrelated environment-wide pytest plugins
(the observed AnyIO deprecation), not BioNet tests or warnings. This suite needs
no external pytest plugin. No tests are xfailed or skipped in the final run.

## Repeated benchmarks

**90 transfers, 90 successes, 0 failures, 90 independently verified hashes.**
Two payload sizes (16,384/65,536 bytes), windows 8/32, three trials per configuration.
18 comparison transfers have no artificial impairment; 72 UDP sweep transfers have
2 ms outbound sender delay and independent loss at both endpoints at 0/.05/.1/.2/.3/.4.
Actual aggregate sender retransmissions: 1,842; simulated sender drops: 1,040;
receiver first-completion drop snapshots: 800. Counters and every trial are in CSV.

Unimpaired comparison, three-trial means (small localhost transfers):

| Bytes | Transport | Window | Goodput Mbps | Completion ms |
|---:|---|---:|---:|---:|
| 16,384 | TCP | N/A | 174.926 | 0.876 |
| 16,384 | UDP | 8 | 89.402 | 1.672 |
| 16,384 | UDP | 32 | 105.983 | 1.243 |
| 65,536 | TCP | N/A | 743.686 | 0.706 |
| 65,536 | UDP | 8 | 174.459 | 3.019 |
| 65,536 | UDP | 32 | 182.180 | 2.881 |

Fixed-size/window UDP sweep: **65,536 bytes, window 32**, three trials per row:

| Loss each direction | Mean goodput Mbps | Mean completion s | Total retries (3 trials) |
|---:|---:|---:|---:|
| 0% | 22.596 | 0.023 | 0 |
| 5% | 1.830 | 0.295 | 25 |
| 10% | 1.299 | 0.465 | 56 |
| 20% | 0.660 | 0.805 | 124 |
| 30% | 0.436 | 1.247 | 210 |
| 40% | 0.252 | 2.099 | 335 |

Raw per-trial values, sample SD, minima/maxima and conditions are in `benchmark/`.
Five PNGs derive only from those measurements; plots disclose success-only means
and failure totals. The TCP comparison and memory plot were visually inspected.
A separate automated injected-failure benchmark test confirms failed rows persist
and contribute to summaries; it is not mixed into the measured benchmark CSV.

These are application implementations on localhost, not transport superiority or
LAN/WAN predictions. TCP uses 64 KiB reads and rereads output to hash; UDP uses
1024-byte packets and incremental receive hashing. Timing excludes source hashing,
receiver startup and independent post-transfer verification. Successful sender
completion includes its handshake/receiver verification. `failure_seconds` instead
includes teardown. Packet/header counters exclude kernel/link overhead; TCP packet
and retransmission counts remain unavailable, not zero. No equal externally
impaired TCP/UDP network comparison, CPU affinity or disk-cache control was run.

## Large files and memory

`tracemalloc` measures both endpoints and streaming hashes in one Python process.
Native/kernel memory, RSS and imports before tracing are excluded. Each case uses
fresh synthetic files in temporary directories; the files are deleted afterwards.
Tracing changes scheduling/timing; these are not ordinary-throughput comparisons.
Window 128, zero injected loss, default 100 ms timeout:

| Protocol | MiB | Seconds (traced) | Goodput Mbps | Retries | Peak Python MiB |
|---|---:|---:|---:|---:|---:|
| UDP | 1 | 0.463 | 18.099 | 174 | 2.129 |
| TCP | 1 | 0.010 | 804.711 | N/A | 2.269 |
| UDP | 10 | 4.644 | 18.063 | 1653 | 2.130 |
| TCP | 10 | 0.027 | 3090.353 | N/A | 2.269 |
| UDP | 100 | 47.657 | 17.602 | 16884 | 2.130 |
| TCP | 100 | 0.211 | 3970.683 | N/A | 2.269 |
| TCP | 1024 | 1.753 | 4899.844 | N/A | 2.268 |

The **traced 1 GiB UDP trial timed out at 240 s**. Its CSV row records failure;
no completion time, hash pass or peak-memory value is claimed. Seven of eight
memory trials succeeded. The first harness version left that killed worker's
synthetic temp directory behind; it was explicitly deleted, and the final harness
places worker data inside the parent's temporary-directory lifetime for cleanup.

A separate **untraced 1 GiB UDP transfer succeeded**, window 32, in
**47.565 s (180.592 Mbps)**, with **0 retransmissions**,
**0 simulated drops** and independent SHA-256 equality. It sent
1,048,576 DATA packets plus START/FIN. The parent imposed a 180-second
limit; see `gib-untraced.json`. Its peak memory is unmeasured. This is a different
window/instrumentation condition, not a replacement for the failed profile.

UDP traced peak was 2.129–2.130 MiB from 1 to 100 MiB; TCP was 2.268–2.269 MiB
through 1 GiB. Together with code inspection this supports bounded streaming
memory under tested settings. It does not certify 1 TiB, maximum-window RSS or all
platforms. Traced UDP retries with zero injected loss reflect local queue/timing
pressure; no claim identifies them as physical-network loss.

## Dashboard timing

Three alternating pairs, 1 MiB, UDP window 128, no tracing, NO_COLOR=1 and stderr
redirected: off mean **0.247509 s**, sample SD **0.157657 s**; on mean **0.094070 s**,
SD **0.058481 s**. All six hashes passed. Scheduling/retransmission variation
outweighs the rendering effect: **overhead is inconclusive**, and no dashboard
speedup or negligible-overhead bound is claimed. Functional tests pass; keep
monitoring disabled for benchmarks and rehearse on the actual macOS terminal.

## Reproduce

Use a network-enabled local executor and fresh output directories:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -ra --junitxml=results/retest.xml
python -m bionet benchmark --output results/rebenchmark --sizes 16384 65536 --windows 8 32 --losses 0 .05 .1 .2 .3 .4 --trials 3
python -m scripts.phase3_profile --output results/reprofile --sizes 1 10 100 1024 --timeout 240
```

The profiling command returns nonzero if any worker times out. Retain failures.
Exact cloud commands and development sequence are in `results/phase3/commands.txt`.
Compilation, CLI without optional site packages and script help passed.
The source/test/script/documentation `git diff --check` passed; the whole-PR
check flags expected traceback whitespace in preserved raw pytest logs. macOS validation script help is not macOS execution.

## Untested / remaining

macOS M4/APFS/Terminal/firewall, actual multi-host LAN/WAN, real biometric ZIP,
physical disk exhaustion/failure, power loss/SIGKILL crash recovery, 1 TiB, maximum
4096-window profiling, long-duration soak/hostile authenticated transport, and equal
external TCP/UDP impairment remain untested. Traced UDP 1 GiB completion is not
validated; its timeout is retained. No encryption/authentication or congestion
control is present. See FINAL_READINESS.md and MACOS_VALIDATION.md.

The final profiling harness also passed a separate forced-timeout cleanup probe:
with a 0.2-second worker budget it reported six timeouts, returned the expected
nonzero status and left the parent-owned temporary directory empty. Actual argv
and assertions are recorded in `profile-timeout-cleanup.json`; these intentional
harness probes are separate from protocol benchmarks and the final pytest count.
The final pytest console duration was **28.98 s**.
