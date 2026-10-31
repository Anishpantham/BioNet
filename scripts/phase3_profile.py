"""Bounded synthetic memory/overhead measurements; each transfer is time-limited.

python -m scripts.phase3_profile --output results/new-profile --sizes 1 10 100
Sizes are MiB. Add 1024 explicitly for a 1 GiB test (at most one source/output pair).
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import tracemalloc
from bionet import sender, tcp_baseline
from bionet.benchmark import local_receiver, synthetic, write_csv
from bionet.integrity import digest


def measure(size, protocol, dashboard, trace, scratch=None, window_size=128):
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        path = Path(directory)/'synthetic.bin'; synthetic(path, size)
        if trace: tracemalloc.start()
        try:
            rx = dict(window_size=window_size, quiet=True) if protocol == 'udp' else {}
            tx = dict(window_size=window_size, timeout=.1, dashboard=dashboard) if protocol == 'udp' else {}
            with local_receiver(protocol, Path(directory)/'out', **rx) as port:
                result = (sender.send if protocol == 'udp' else tcp_baseline.send)(path, port=port, **tx)
            result['independent_sha256'] = digest(path) == digest(Path(directory)/'out'/path.name)
            if trace: result['peak_python_bytes'] = tracemalloc.get_traced_memory()[1]
            result.update(protocol=protocol, size=size, dashboard=dashboard, tracemalloc=trace)
            result.pop('session', None); result.pop('filename', None)
            return result
        finally:
            if trace: tracemalloc.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--sizes', type=int, nargs='+', default=[1, 10, 100])
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--window-size', type=int, default=128)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--protocol', choices=['udp','tcp'], default='udp')
    parser.add_argument('--dashboard', action='store_true')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    if any(not 1 <= size <= 1024 for size in args.sizes): parser.error('sizes must be 1..1024 MiB')
    if not 1 <= args.window_size <= 4096: parser.error('window must be 1..4096')
    root = Path(args.output)
    if args.worker:
        root.write_text(json.dumps(measure(args.sizes[0]<<20, args.protocol, args.dashboard, args.trace, root.parent, args.window_size)))
        return
    root.mkdir(parents=True, exist_ok=False)
    (root/'conditions.json').write_text(json.dumps(dict(python=sys.version, platform=platform.platform(),
        sizes_mib=args.sizes, per_transfer_timeout=args.timeout, window=args.window_size, loss=0, payload='bytes 0..255',
        memory='tracemalloc includes both endpoints and streaming hashes, excludes native/kernel allocations',
        timing='sender result; source pre-hash excluded; traced timings are instrumented',
        overhead='3 alternating dashboard off/on UDP pairs, 1 MiB, stderr redirected, NO_COLOR=1'), indent=2)+'\n')
    jobs = [('memory', size, protocol, False, True, 0) for size in args.sizes for protocol in ('udp','tcp')]
    for trial in range(3):
        jobs.extend(('dashboard',1,'udp',enabled,False,trial) for enabled in ([False,True] if trial%2==0 else [True,False]))
    rows = []
    for index, (experiment, size, protocol, dashboard, trace, trial) in enumerate(jobs):
        row = dict(experiment=experiment, size=size<<20, protocol=protocol, dashboard=dashboard,
                   tracemalloc=trace, trial=trial, success=False, sha256=False)
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory)/'result.json'
            cmd = [sys.executable,'-m','scripts.phase3_profile','--worker','--output',str(result_path),'--sizes',str(size),'--protocol',protocol,'--window-size',str(args.window_size)]
            if dashboard: cmd.append('--dashboard')
            if trace: cmd.append('--trace')
            try:
                with (root/f'trial-{index}.log').open('w') as log:
                    subprocess.run(cmd, check=True, timeout=args.timeout, stdout=log, stderr=log,
                                   env=dict(os.environ, NO_COLOR='1'))
                row.update(json.loads(result_path.read_text()))
            except (OSError, subprocess.SubprocessError) as exc:
                row['error'] = str(exc)
        rows.append(row); write_csv(root/'measurements.csv', rows)
        print(json.dumps(row), flush=True)
    plot_memory(root, rows, args.window_size)
    if any(not r['success'] or not r.get('independent_sha256') for r in rows):
        raise SystemExit('A measurement failed; inspect CSV and trial logs.')


def plot_memory(root, rows, window_size=128):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    for protocol in ('udp','tcp'):
        values = [r for r in rows if r['experiment']=='memory' and r['protocol']==protocol and r['success']]
        ax.plot([r['size']/(1<<20) for r in values], [r['peak_python_bytes']/(1<<20) for r in values], 'o-', label=protocol.upper())
    ax.set(xlabel='File size (MiB)', ylabel='Peak traced Python allocations (MiB)', title=f'Measured localhost memory; both endpoints; window {window_size}')
    ax.set_xscale('log'); ax.set_ylim(bottom=0)
    ax.legend()
    samples = [r for r in rows if r['experiment'] == 'memory']
    failures = sum(not r['success'] for r in samples)
    fig.text(.5, .01, f'Successes plotted; {failures}/{len(samples)} profiling failures (see measurements.csv)',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .03, 1, 1)); fig.savefig(root/'memory.png'); plt.close(fig)


if __name__ == '__main__': main()
