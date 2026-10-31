"""Guided ~3-minute synthetic-only demo: python -m scripts.demo."""
import argparse
import json
import random
import tempfile
import zipfile
from pathlib import Path
from bionet.benchmark import local_receiver, run
from bionet.integrity import digest
from bionet.sender import send


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='results/demo')
    parser.add_argument('--non-interactive', action='store_true', help='skip presenter pauses')
    parser.add_argument('--no-dashboard', action='store_true', help='use ACK/retry text instead of Rich')
    args = parser.parse_args()
    def stage(text):
        print('\n'+text, flush=True)
        if not args.non_interactive:
            input('Press Enter to continue… ')
    root = Path(args.output)
    if root.exists():
        parser.error('choose a fresh --output directory to preserve previous evidence')
    root.mkdir(parents=True)
    stage('0:00–0:25 | UDP lacks reliable ordered delivery. BioNet adds individual ACKs,\n'
          'a bounded sliding window and per-packet timers. All bytes today are synthetic.')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'synthetic.zip'
        rng = random.Random(42)
        with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as archive:
            with archive.open('synthetic.bin', 'w', force_zip64=True) as stream:
                for _ in range(4):
                    stream.write(rng.randbytes(65536))
        records = []
        for label, loss, reorder in [('Reliable transfer', 0, 0), ('Loss and reordering', .1, .3)]:
            stage(('0:25–0:55' if not loss else '0:55–1:50') + f' | {label}: starting UDP receiver, then sender.\n'
                  f'Loss per direction={loss:.0%}; sender reordering={reorder:.0%}.\n'
                  'Watch base stop at a hole while later ACKs turn green; only missing packets retry.')
            completion = []
            destination = Path(directory)/('loss' if loss else 'clean')
            with local_receiver('udp', destination, window_size=8, loss=loss, seed=107,
                                quiet=True, on_complete=completion.append) as port:
                print(f'Receiver ready on 127.0.0.1:{port}; launching sender with window 8.', flush=True)
                result = send(path, port=port, window_size=8, loss=loss, reorder=reorder,
                              latency=.002, seed=7, dashboard=not args.no_dashboard, verbose=args.no_dashboard)
            verified = digest(path) == digest(destination/path.name)
            if not verified:
                raise RuntimeError('independent SHA-256 check failed')
            record = dict(scenario=label, sender=result, receiver=completion[0], independent_sha256=verified)
            records.append(record)
            print(f"Reconstruction SHA-256 PASS; {result['seconds']:.3f} s; {result['goodput_mbps']:.3f} Mbps; "
                  f"{result['retransmissions']} retries; {completion[0]['out_of_order']} out-of-order arrivals.")
        (root/'transfer_evidence.json').write_text(json.dumps(records, indent=2)+'\n')
    stage('1:50–2:35 | Compare TCP and UDP with identical synthetic payloads, no artificial\n'
          'delay or loss, and dashboards disabled. Two short measured trials per configuration.\n'
          'The separate UDP loss sweep is not a fair impaired-TCP comparison.')
    rows = run(root/'benchmark', trials=2, sizes=(65536,), windows=(8, 32), losses=(0, .1))
    for row in rows:
        if row['experiment'] == 'comparison':
            if row['success']:
                print(f"{row['protocol'].upper()} window={row['window']}: {row['goodput_mbps']:.3f} Mbps, {row['seconds']:.4f} s")
            else:
                print(f"{row['protocol'].upper()}: FAILED: {row['error']}")
    stage('2:35–3:00 | Open tcp_udp_comparison.png and summary.csv in the benchmark directory.\n'
          'CRC32 checks packets; SHA-256 checks reconstructed bytes. Neither authenticates\n'
          'or encrypts. Localhost measurements do not establish LAN/WAN superiority.\n'
          f'Evidence saved under {root}; temporary synthetic ZIPs have been deleted.')
    if any(not row['success'] for row in rows):
        raise SystemExit('Some benchmark trials failed; inspect the CSV.')


if __name__ == '__main__':
    main()
