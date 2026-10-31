# Phase 2 implementation review

Base: merged PR #1, `97adb38494aeb9bc01a79e4072bbc5817b55f826`.

| Area | Already present | Phase 2 change |
|---|---|---|
| Architecture/CLI | Separate codec, impairment, sender, receiver, hashing, TCP and benchmark modules | Retain modules and commands; optional dashboard, benchmark configuration flags |
| Selective Repeat | Independent timers, negotiated bounded window, individual ACKs, out-of-order buffer, control retries | Preserve v1 wire format; bounded window visualization and arrival counters |
| Integrity/large files | Streamed input, temporary output, streaming hash, no-clobber publish | Hash UDP reconstruction while writing; explicit 1 TiB and sequence bounds; fail promptly on truncated source |
| TCP | Working streamed baseline and verified completion | Automated equal-condition comparison; application byte accounting |
| Experiments | UDP sweep, CSV, four mean plots, historical measurements | Separate fair comparison, fifth plot, SD error bars, summary CSV, machine/condition manifest, persisted failed trials |
| Demo/docs | Manual demo and initial report/viva material | Executable guided synthetic ZIP demonstration, dashboard guide, updated short report and submission checklist |
| Tests | Core codec, controls, loss, cleanup, binary/TCP integration | Focused Phase 2 smoke tests; comprehensive final validation remains separate |

No real biometric data was accessed. No resume protocol or unrelated features were added.
