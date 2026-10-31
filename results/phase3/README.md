# Phase 3 executed evidence

All payloads were synthetic. No biometric data is present. Previous-phase results
elsewhere in `results/` are historical; this directory contains new runs.

- `environment.json`: exact Python/platform/package versions and audited base SHA.
- `baseline-tests.log`: first run without sandbox socket permission (environment failure).
- `baseline-network-tests.log`: all 45 original tests passed after enabling sockets.
- `regressions-before.log`: first regression development run, including one fixture error.
- `regressions-before-confirmed.log`: corrected pre-fix selection, 16 failures / 5 passes.
- `regressions-after.log`: same selection, 21 passes after code fixes.
- `expanded-tests.log`: first 97 expanded tests passed; later additions are in full suite.
- `full-tests.log`, `full-tests.xml`: full suite, see final report for final count.
- `benchmark/`: actual three-trial CSV, failure-aware summary, conditions and five PNGs.
- `profile/`: bounded worker measurements, logs, conditions and measured memory PNG.
  The traced 1 GiB UDP timeout remains a failed row; no peak/completion was fabricated.
- CLI and macOS script help logs: entry-point/import checks, not macOS execution.

Profiling and benchmarking were run separately. Source/hash allocation peaks exclude
native/kernel memory; tracing perturbs timing. Dashboard stdout/stderr was redirected.
Read `docs/PHASE3_TEST_RESULTS.md` and `docs/FINAL_READINESS.md` for interpretation.

`gib-untraced.json` records the separate verified 1 GiB UDP transfer at window 32.
`profile-timeout-cleanup.json` records the final harness's intentional short-timeout
probe: exit 1 was expected and the parent-owned temp directory was empty afterwards.
These induced harness failures are not included in the 90 benchmark trials or in
pytest's final failure count.

Raw pytest logs retain their original traceback whitespace. A whole-PR whitespace
check reports those artifact lines; the separate source/test/script/documentation
whitespace check passes. Logs were not rewritten to make that check silent.
