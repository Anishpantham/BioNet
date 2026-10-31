# MacBook Air M4 validation (local only; not executed in cloud)

The cloud host is Linux x86_64/Python 3.12.14. **No macOS test pass is claimed.**
Code inspection found no platform-specific runtime blocker. Confirm APFS hard-link
publication, Python arm64 build, real terminal behavior and firewall permissions.

On the Mac, in a checkout of this PR:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m scripts.validate_macos --output results/macos-local
# Optional 1 GiB synthetic profiling (needs several GiB free and extra time):
python -m scripts.validate_macos --output results/macos-gib --gib
```

Use a fresh output directory. The script requires Darwin/arm64 and Python 3.12+,
runs the full suite, three-trial benchmarks and bounded memory profiling, saves
commands/exit status/logs/plots, and returns failure if any stage fails. All payloads
are synthetic. Inspect timed-out trials instead of interpreting them as passes.

Also rehearse `python -m scripts.demo --output results/mac-demo` in Terminal,
with default colors, `NO_COLOR=1`, window resizing and Ctrl-C. Repeat in two terminal
processes and then on a trusted private LAN with synthetic data. Explicitly permit
Python's incoming UDP/TCP traffic if macOS prompts; bind only the required interface.
Verify both endpoints with `shasum -a 256` and inspect loss/window counters. Rehearse
with AC power and normal thermal conditions; do not compare cloud timings to M4
as a controlled hardware experiment. No LAN/WAN throughput is certified here.

## Actual biometric ZIP: local-only steps after validation

Keep `25BCS126.zip` outside the repository and cloud-synced folders. Do not upload it,
attach it to this chat, or include it in test logs/Git. The cloud work never reads it.
For an initial same-machine check (run these commands only on your Mac):

```sh
# Terminal 1: destination outside the repository; it must not contain that filename.
python -m bionet receiver --host 127.0.0.1 --port 9000 --output /private/tmp/bionet-local-received
# Terminal 2: replace with your existing local path; keep the source stable.
python -m bionet sender --host 127.0.0.1 --port 9000 --file /LOCAL/PRIVATE/PATH/25BCS126.zip --window-size 32
shasum -a 256 /LOCAL/PRIVATE/PATH/25BCS126.zip /private/tmp/bionet-local-received/25BCS126.zip
cmp /LOCAL/PRIVATE/PATH/25BCS126.zip /private/tmp/bionet-local-received/25BCS126.zip
```

Use a user-private destination (create it with `mkdir -m 700` first). For the
assignment LAN demo, repeat the already-validated synthetic LAN configuration,
using receiver private IPv4 addresses and appropriately private destination storage.
CRC32/SHA-256 are **not encryption or authentication**. Use only trusted hosts and
networks; do not expose the receiver to the Internet. Do not display/extract archive
contents. Keep logs local; retain only necessary non-sensitive assignment evidence.
Clean up extra local copies according to your data-handling requirements.
