"""Measured localhost trials; all payloads are synthetic."""
import csv
import itertools
import queue
import tempfile
import threading
from pathlib import Path
from .sender import send
from .receiver import receive

def run(output='results', trials=3, sizes=(65536, 262144), windows=(8, 32), losses=(0, .05, .1, .2)):
    if trials < 1:
        raise ValueError('trials must be positive')
    root = Path(output); root.mkdir(parents=True, exist_ok=True); rows = []
    for size, window, loss, trial in itertools.product(sizes, windows, losses, range(trials)):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.bin'
            with path.open('wb') as stream:
                for offset in range(0, size, 65536):
                    stream.write((bytes(range(256))*256)[:min(65536, size-offset)])
            stop = threading.Event(); ports = queue.Queue()
            worker = threading.Thread(target=receive, kwargs=dict(port=0, output=Path(directory)/'out', stop=stop, ready=ports.put, loss=loss, seed=trial+100), daemon=True)
            worker.start(); port = ports.get(timeout=5)
            try:
                result = send(path, port=port, window_size=window, loss=loss, seed=trial, latency=.002)
            except (TimeoutError, RuntimeError) as exc:
                result = dict(success=False, sha256=False, error=str(exc))
            finally:
                stop.set(); worker.join(2)
            rows.append(dict(result, size=size, window=window, loss=loss, trial=trial))
    fields = sorted(set().union(*(row.keys() for row in rows)))
    with (root/'benchmark_results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    plot(root)
    return rows

def plot(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import statistics
    root = Path(root)
    with (root/'benchmark_results.csv').open() as stream:
        rows = [r for r in csv.DictReader(stream) if r['success'] == 'True']
    for x, y, filename, ylabel in [('loss','goodput_mbps','throughput_loss','Goodput (Mbps)'), ('loss','seconds','time_loss','Completion time (s)'), ('loss','retransmissions','retransmissions_loss','Retransmissions'), ('window','goodput_mbps','throughput_window','Goodput (Mbps)')]:
        fig, ax = plt.subplots()
        group_key = 'window' if x == 'loss' else 'loss'
        for size, group in sorted({(r['size'], r[group_key]) for r in rows}):
            subset = [r for r in rows if r['size'] == size and r[group_key] == group]
            values = sorted({float(r[x]) for r in subset})
            ax.plot(values, [statistics.mean(float(r[y]) for r in subset if float(r[x]) == v) for v in values], marker='o', label=f'{size} B, {group_key}={group}')
        ax.set(xlabel='Configured loss probability' if x == 'loss' else 'Window (packets)', ylabel=ylabel, title='Localhost UDP; 2 ms sender delay; mean of trials')
        ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(root/(filename+'.png')); plt.close(fig)
