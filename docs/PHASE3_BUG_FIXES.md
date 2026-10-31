# Phase 3 defects and fixes

The initial targeted regression selection demonstrated **16 failures / 5 passes**
against merged Phase 2; after the first fixes the same 21 cases passed. Raw before/
after logs are in `results/phase3/`. Additional regressions cover refinements below.
No tests were weakened to obtain passing results.

| Defect | Root cause and smallest fix | Regression evidence |
|---|---|---|
| UDP service exits on disk write/flush error | File operations escaped the receive loop. Catch session I/O failure, close/delete owned temp, clear session and send ERROR; never FIN_ACK. Cleanup runs even if close fails. | Injected write and FIN flush failures; subsequent START accepted; publish failure and SIGINT cleanup |
| TCP deletes someone else's `.part` | Unconditional finally-unlink after failed exclusive open. Track successful temp ownership. | Fixed UUID colliding with pre-existing bytes; FAIL returned and bytes preserved |
| UDP cleanup retains stale ownership | Completed/expired/rejected temp path remained referenced. Clear it after unlink. | Recreate same temp path after completed transfer; receiver shutdown preserves new owner's bytes |
| Non-finite/fractional limits accepted | Range comparisons admit NaN/infinite timeout/delay or float window/retry; can hang, never expire or raise packing errors. Validate finite time values and integral counts before I/O. | NaN/infinity scheduler and timeout, fractional retry/window cases |
| Invalid sequence Python values accepted | Boolean packed as sequence; float leaked struct.error. Require actual int sequence/type plus existing 64-bit bounds. | True, float, negative, overflow; MAX_SEQUENCE still round-trips |
| Malformed control messages accepted | Kind alone satisfied sender control; receiver accepted nonzero control sequence. Check zero control sequence and empty FIN/FIN_ACK; payload-bearing DATA ACKs ignored. | Raw invalid START/FIN and injected malformed FIN_ACKs; valid FIN retry remains supported |
| Invalid traffic holds session alive | `last` refreshed before DATA validation; repeated START did not refresh it and conflicting metadata was silently acknowledged. Refresh only valid DATA/repeated matching START; reject conflicting START. | Invalid sequence traffic through idle timeout; matching duplicate START retains reorder progress; conflicting metadata errors |
| Metadata helper lacks its documented cap | Transport limited input, but shared validator accepted >1200 bytes. Enforce size at shared API. Normalize RecursionError defensively. | Oversized helper payload; malformed/deep input through UDP/TCP. Deep JSON already rejected on this runtime, so no parser-crash claim |
| Failure presentation incomplete | CSV summarized failures, but plots silently showed only successes and failure timing was absent. Label counts on each plot and record separate failure_seconds. | Injected failed UDP benchmark trials remain in raw/summary CSV with duration |

The early development log `regressions-before.log` also contains one test-fixture
error: its TCP recovery source and destination were initially the same directory.
The fixture was corrected before the confirmed baseline log; this was not a
product defect. The existing deep JSON cases already rejected those inputs on
this runtime. Initial sandbox failures are environment failures, not bugs fixed
in the network protocol. See PHASE3_TEST_RESULTS.md for the final full-suite result.

Packet format/version, chunk/window defaults, retry strategy and file hash contract
remain compatible with Phase 2. No retransmission-algorithm rebuild was needed.
