"""Measured synthetic localhost experiments; comparisons have no UDP-only delay."""
import csv
import itertools
import json
import platform
import queue
import statistics
import sys
import tempfile
import threading
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from . import sender, receiver, tcp_baseline
from .integrity import digest


def synthetic(path, size):
    """Stable bytes, generated in bounded blocks; never reads a dataset."""
    block = bytes(range(256)) * 256
    with Path(path).open('xb') as stream:
        for offset in range(0, size, len(block)):
            stream.write(block[:min(len(block), size-offset)])


@contextmanager
def local_receiver(protocol, output, **options):
    stop = threading.Event(); ports = queue.Queue(); errors = queue.Queue()
    receive = receiver.receive if protocol == 'udp' else tcp_baseline.receive
    def serve():
        try:
            receive(port=0, output=output, stop=stop, ready=ports.put, **options)
        except BaseException as exc:
            errors.put(exc)
    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        try:
            port = ports.get(timeout=5)
        except queue.Empty:
            if not errors.empty():
                raise errors.get()
            raise RuntimeError('receiver startup timed out')
        yield port
    finally:
        stop.set(); worker.join(12)
        if worker.is_alive():
            raise RuntimeError('receiver did not stop')
        if not errors.empty():
            raise errors.get()


def write_csv(path, rows):
    fields = sorted(set().union(*(row.keys() for row in rows)))
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def summarize(rows):
    groups = defaultdict(list)
    keys = ('experiment', 'protocol', 'size', 'window', 'loss', 'sender_latency')
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    summary = []
    for key, group in groups.items():
        successful = [r for r in group if r['success']]
        item = dict(zip(keys, key), trials=len(group), successes=len(successful), failures=len(group)-len(successful))
        for metric in ('goodput_mbps', 'seconds', 'retransmissions', 'application_overhead_bytes'):
            values = [r[metric] for r in successful if metric in r]
            if values:
                item.update({metric+'_mean': statistics.mean(values),
                             metric+'_stdev': statistics.stdev(values) if len(values)>1 else '',
                             metric+'_min': min(values), metric+'_max': max(values)})
        summary.append(item)
    return summary


def run(output='results/phase2', trials=3, sizes=(65536, 262144), windows=(8, 32), losses=(0, .05, .1, .2), no_plots=False):
    if trials < 1 or not sizes or not windows or not losses:
        raise ValueError('positive trials and nonempty parameter lists required')
    if any(not 0 < s <= 1 << 40 for s in sizes) or any(not 1 <= w <= 4096 for w in windows) or any(not 0 <= p < 1 for p in losses):
        raise ValueError('invalid experiment parameters')
    root = Path(output); root.mkdir(parents=True, exist_ok=True)
    if (root/'benchmark_results.csv').exists():
        raise ValueError('results already exist; choose a fresh --output directory')
    manifest = dict(measured=True, utc=datetime.now(timezone.utc).isoformat(), python=sys.version,
                    platform=platform.platform(), trials=trials, sizes=list(sizes), windows=list(windows),
                    losses=list(losses), payload='repeating bytes 0..255, no compression',
                    host='127.0.0.1, sender and receiver threads in one process',
                    chunk=1024, timeout=.1, retries=50, dashboard=False,
                    comparison='no artificial impairment; alternate TCP/UDP order each trial',
                    udp_sweep='2 ms sender delay; independent loss both endpoints',
                    timing='after source hash through receiver verification reply; receiver startup excluded',
                    overhead='application bytes observed at sender minus useful payload; excludes TCP/IP and link headers')
    (root/'conditions.json').write_text(json.dumps(manifest, indent=2)+'\n')
    rows = []
    # TCP has no SR window: measure it once per size/trial, not once per UDP window.
    jobs = []
    for size, trial in itertools.product(sizes, range(trials)):
        pair = [('tcp', 0)] + [('udp', w) for w in windows]
        if trial % 2:
            pair.reverse()
        jobs.extend(('comparison', p, size, w, 0, trial, 0) for p, w in pair)
    jobs.extend(('udp_sweep', 'udp', s, w, loss, t, .002)
                for s, w, loss, t in itertools.product(sizes, windows, losses, range(trials)))
    for experiment, protocol, size, window, loss, trial, latency in jobs:
        result = dict(success=False, sha256=False)
        completed = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic.bin'; synthetic(path, size)
            rx = dict(window_size=window, loss=loss, seed=trial+100, quiet=True, on_complete=completed.append) if protocol == 'udp' else {}
            tx = dict(window_size=window, loss=loss, seed=trial, latency=latency) if protocol == 'udp' else {}
            try:
                with local_receiver(protocol, Path(directory)/'out', **rx) as port:
                    send = sender.send if protocol == 'udp' else tcp_baseline.send
                    result = send(path, port=port, **tx)
                if digest(path) != digest(Path(directory)/'out'/path.name):
                    raise RuntimeError('independent reconstruction hash mismatch')
                if completed:
                    result.update(receiver_simulated_drops=completed[0]['simulated_drops'],
                                  out_of_order=completed[0]['out_of_order'])
            except (OSError, RuntimeError, ValueError) as exc:
                result.update(success=False, sha256=False, error=str(exc))
            result.pop('session', None); result.pop('filename', None)
            rows.append(dict(result, experiment=experiment, protocol=protocol, size=size, window=window,
                             loss=loss, trial=trial, sender_seed=trial, receiver_seed=trial+100,
                             sender_latency=latency, payload_sha256=digest(path)))
        # Keep every completed trial, including failures, even if a later run is interrupted.
        write_csv(root/'benchmark_results.csv', rows)
        write_csv(root/'summary.csv', summarize(rows))
    if not no_plots:
        plot(root)
    return rows


def plot(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root = Path(root)
    with (root/'benchmark_results.csv').open() as stream:
        rows = [r for r in csv.DictReader(stream) if r['success'] == 'True']
    sweep = [r for r in rows if r.get('experiment', 'udp_sweep') == 'udp_sweep']
    for x, y, filename, ylabel in [('loss','goodput_mbps','throughput_loss','Goodput (Mbps)'), ('loss','seconds','time_loss','Completion time (s)'), ('loss','retransmissions','retransmissions_loss','Retransmissions'), ('window','goodput_mbps','throughput_window','Goodput (Mbps)')]:
        fig, ax = plt.subplots()
        group_key = 'window' if x == 'loss' else 'loss'
        for size, group in sorted({(r['size'], r[group_key]) for r in sweep}):
            subset = [r for r in sweep if r['size'] == size and r[group_key] == group]
            values = sorted({float(r[x]) for r in subset})
            samples = [[float(r[y]) for r in subset if float(r[x]) == v] for v in values]
            ax.errorbar(values, [statistics.mean(v) for v in samples],
                        yerr=[statistics.stdev(v) if len(v)>1 else 0 for v in samples],
                        marker='o', capsize=3, label=f'{size} B, {group_key}={group}')
        ax.set(xlabel='Configured loss probability (each direction)' if x == 'loss' else 'Window (packets)', ylabel=ylabel, title='Measured localhost UDP; 2 ms sender delay; mean ± sample SD')
        if sweep:
            ax.legend(fontsize=7)
        else:
            ax.text(.5, .5, 'No successful measurements', ha='center', transform=ax.transAxes)
        fig.tight_layout(); fig.savefig(root/(filename+'.png')); plt.close(fig)
    comparison = [r for r in rows if r.get('experiment') == 'comparison']
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, metric, label in zip(axes, ('goodput_mbps', 'seconds'), ('Goodput (Mbps)', 'Completion time (s)')):
        groups = defaultdict(list)
        for row in comparison:
            groups[(int(row['size']), row['protocol'], int(row['window']))].append(float(row[metric]))
        labels, means, errors = [], [], []
        for (size, protocol, window), values in sorted(groups.items()):
            labels.append(f'{size} B\n{protocol.upper()}'+(f' W={window}' if window else ''))
            means.append(statistics.mean(values)); errors.append(statistics.stdev(values) if len(values)>1 else 0)
        ax.bar(range(len(means)), means, yerr=errors, capsize=3)
        ax.set_xticks(range(len(labels)), labels, fontsize=7); ax.set_ylabel(label)
        if not groups:
            ax.text(.5, .5, 'No successful comparison measurements', ha='center', transform=ax.transAxes)
    fig.suptitle('Measured localhost TCP vs UDP; no artificial impairment; mean ± sample SD')
    fig.tight_layout(); fig.savefig(root/'tcp_udp_comparison.png'); plt.close(fig)
