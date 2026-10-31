# Phase 2 smoke validation — 31 October 2026

These are executed smoke checks, not comprehensive final validation.

## Tests actually executed

- Focused final selection: **22 passed, 23 deselected** in 1.91 s. Covers the seven
  Phase 2 tests, TCP baseline, retry exhaustion, metadata limits, interrupted/hash
  failure cleanup, and four lost-control-message cases.
- Separate UDP empty file and 1025-byte boundary cases: **2 passed** in 0.22 s.
- Total final focused coverage: **24 passing test cases**. Earlier development
  selection also passed 17 cases before the final cleanup/monitoring refinements.
- `compileall` for package/scripts/tests; CLI help for sender, benchmark and demo;
  experiment wrapper help; base CLI import with `python -S` (without optional
  site packages); synthetic ZIP generator with a 65,537-byte payload; `git diff --check`.
- Executed guided demo in non-interactive mode with Rich enabled: both synthetic
  ZIP transfers passed receiver and independent streaming hash checks. It also ran
  14 measured benchmark transfers (six comparison, eight UDP sweep), all successful,
  and generated all five PNGs. Comparison plot visually inspected.

Reproduce focused tests from the repository root:

```sh
python -m pytest -q tests/test_phase2.py tests/test_bionet.py -k 'phase2 or tcp or retry_exhaustion or interrupted_and_hash_failure or metadata_limits or lost_controls'
python -m pytest -q 'tests/test_bionet.py::test_udp[0-0]' 'tests/test_bionet.py::test_udp[0-1025]'
python -m scripts.demo --non-interactive --output results/new-demo-run
```

Initial socket tests were attempted without the executor's network permission:
8 failed, 9 passed, 27 deselected; socket creation raised PermissionError and
receiver readiness timed out. Enabling network access for the same command resolved
that environment issue (17 passed). These failed attempts are not hidden or counted
as protocol failures. Matplotlib also warned about an unwritable home cache and
successfully used a temporary cache directory; all plots were produced.

## Measured smoke evidence

`results/phase2-smoke/transfer_evidence.json` and `benchmark/` are copied verbatim
from the executed synthetic demonstration's output. Test logs are alongside them.
Original Phase 1 results remain untouched. No illustrative values are mixed into
these CSVs. Conditions and seeds are recorded in `benchmark/conditions.json`.

Two trials, 65,536-byte payload, no artificial impairment, localhost:

|Implementation|Mean goodput Mbps|Mean completion ms|Successes|
|---|---:|---:|---:|
|TCP|1260.671|0.418|2/2|
|UDP window 8|207.134|2.534|2/2|
|UDP window 32|207.849|2.524|2/2|

The lossy synthetic ZIP demo recorded 61 retransmissions, 38 sender simulated
drops and 147 out-of-order arrivals, followed by verified reconstruction. Counts
can change with scheduling. Small files and sub-millisecond TCP timings make these
smoke measurements unsuitable for broad performance conclusions. They do not show
UDP superiority. See the raw CSV and SD fields before interpreting any average.

## Not executed in this phase

Full suite; all default three-trial/size/window/loss combinations; GiB/TiB transfers
or peak-memory profiling; disk-full/power-loss/SIGKILL scenarios; controlled equal
network impairment for TCP/UDP; sustained load/WAN/LAN/multi-machine testing;
macOS/Apple Silicon checks; dashboard timing-overhead profiling; interactive
three-minute presentation rehearsal; actual biometric transfer; final two-page PDF
pagination. These remain explicitly reserved for final testing/evaluation.
