# Final readiness assessment

**Ready for a controlled synthetic university demonstration on the tested Linux
host; final MacBook/LAN sign-off remains conditional on local validation.**

- Final automated suite: **181 passed, 0 failed, 0 skipped**.
- Genuine Selective Repeat proven with packet traces: only missing DATA retries,
  individual timers/ACKs, bounded windows/buffering, correct contiguous advancement.
- 90/90 measured benchmark transfers verified, including independent loss up to
  40% each direction; three trials per configuration and honest failure summaries.
- 1 GiB UDP completed untraced in 47.565 s with zero retries and matching
  SHA-256. UDP traced peak stays ~2.13 MiB through 100 MiB; TCP ~2.27 MiB through 1 GiB.
- The traced 1 GiB UDP case exceeded 240 s; its memory/completion remain unvalidated.
  This is retained as a failed experiment, separate from zero failing pytest tests.
- Disk-I/O containment, temp ownership, malformed control handling, invalid limits,
  idle expiry and measurement reporting fixes are documented in PHASE3_BUG_FIXES.md.
- Optional/no-color dashboard, empty/failed transfer display, streamed TCP framing,
  subprocess interruption and safe publication have executed tests.

## Before the university demonstration

Run `python -m scripts.validate_macos` on the actual M4 with Python 3.12+; rehearse
Terminal rendering and the two-process demo. Validate trusted LAN networking with
synthetic files before following local-only biometric ZIP instructions. The cloud
has not accessed that ZIP or certified macOS/LAN operation. Obtain instructor
approval, finish report pagination and rehearse the viva as listed in the existing
submission checklist. These non-code steps are not marked complete by this PR.

## Operational limits

Single active UDP session, finite retries and a 120-second/1024-entry completion
cache. Choose compatible timeouts; completion can be ambiguous if replies are lost
or the receiver restarts. Graceful cleanup is tested; crashes/unlink failures can
leave partials. Source files must stay stable and output directories must be
private. No encryption, authentication, congestion control, resume or Internet
hardening. Integrity checks do not protect biometric confidentiality.

Localhost/seeded impairment is not a real-network equivalence claim. Measured
dashboard overhead was inconclusive, so benchmarks disable it. Peak Python
allocation is not RSS, and one successful GiB transfer is not a sustained-soak
qualification. Physical disk failure, power loss and macOS hardware remain outside
executed evidence. The pull request is for review and must not be auto-merged.
