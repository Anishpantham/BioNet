# Submission checklist — assignment deadline 10 November 2026

This checklist maps the supplied assignment to evidence and pending work. A checked
implementation item is not a claim of comprehensive final validation.

- [x] Continue merged PR #1 on a new feature branch; preserve protocol version 1.
- [x] Genuine UDP sockets and Selective Repeat, per-packet ACKs/timers, bounded windows.
- [x] Reconstruction, size/SHA-256 verification, atomic no-clobber publication.
- [x] Streamed source/output and bounded memory design; explicit sequence/size limits.
- [x] Optional metadata-only dashboard and compact colored sliding window.
- [x] TCP baseline and automated equal-condition synthetic comparison.
- [x] At least two performance metrics: completion time and goodput; retries/overhead too.
- [x] Repeated-trial raw CSV, summaries, five measured plots and experimental conditions.
- [x] Synthetic-only guided ~3-minute demo and individual viva guide.
- [x] Source/configuration, architecture and sequence diagrams, concise report draft.
- [ ] Obtain instructor approval for Selective Repeat as the chosen mechanism.
- [ ] Dedicated final phase: complete suite, stress/large-file memory, interruption,
  disk-full, process termination, platform and sustained-loss validation.
- [ ] Run final >=3-trial controlled experiments; include successes AND failures.
- [ ] Confirm final two-process/two-machine LAN demo on trusted local machines.
- [ ] Transmit actual captured biometric ZIP locally for the assignment; never upload
  it to cloud/GitHub. Verify byte equality/SHA-256 and retain only non-sensitive evidence.
- [ ] Typeset TECHNICAL_REPORT.md to exactly two pages and inspect exported PDF.
- [ ] Rehearse the demo and individual viva with all three team members.
- [ ] Review/merge Phase 2 PR after review; assemble code, report, diagrams, measured
  results and logs for submission by the deadline.
