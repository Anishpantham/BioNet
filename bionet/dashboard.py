"""Optional, bounded metadata-only display; no payloads enter this module."""
import time


class Dashboard:
    def __init__(self, enabled=False, role='sender'):
        self.enabled, self.role = enabled, role
        self.live = None
        self.last = 0.0
        self.started = time.monotonic()
        self.state = dict(status='Waiting', verified='Pending')

    def __enter__(self):
        if self.enabled:
            try:
                from rich.console import Console
                from rich.live import Live
            except ImportError as exc:
                raise RuntimeError('Dashboard requires: pip install "bionet[dashboard]"') from exc
            self.live = Live(self.render(), console=Console(stderr=True), refresh_per_second=5)
            self.live.start()
        return self

    def update(self, force=False, **values):
        if not self.enabled:
            return
        self.state.update(values)
        now = time.monotonic()
        if force or now - self.last >= .2:
            self.last = now
            self.live.update(self.render())

    def render(self):
        from rich.console import Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        s = self.state
        elapsed = s.get('elapsed', time.monotonic() - self.started)
        size, done = s.get('size', 0), s.get('done', 0)
        percent = 100 * done / size if size else (100 if s['verified'] == 'PASS' else 0)
        table = Table.grid(expand=True, padding=(0, 2))
        table.add_column(); table.add_column()
        table.add_row(f"Progress {percent:6.2f}%  {done:,}/{size:,} payload bytes", f"Elapsed {elapsed:.2f} s")
        table.add_row(f"TX {s.get('tx', 0):,} B / RX {s.get('rx', 0):,} B (BioNet datagrams)", f"Current goodput {s.get('rate', 0):.3f} Mbps")
        table.add_row(f"Total DATA {s.get('total', 0):,} / acknowledged {s.get('acked', 0):,}", f"Outstanding {s.get('outstanding', 0)}")
        table.add_row(f"Window base {s.get('base', 0):,} / width {s.get('width', 0)}", f"Retransmissions {s.get('retries', 'N/A')}")
        table.add_row(f"Simulated outbound drops {s.get('drops', 0)}", f"Out-of-order arrivals {s.get('out_of_order', 'N/A')}")
        window = Text()
        colors = {'A': 'green', 'P': 'yellow', 'L': 'red', 'R': 'magenta', '.': 'dim'}
        for seq, code in s.get('cells', ()):
            window.append(f'{seq}:{code} ', style=colors[code])
        return Panel(Group(table, window, Text('A ACKed   P pending   L simulated drop   R retried   . unsent (first 32 slots)'),
                           Text(f"{s['status']} | SHA-256: {s['verified']}")), title=f'BioNet · {self.role}')

    def __exit__(self, kind, value, tb):
        if self.live:
            if kind:
                self.update(force=True, status='Interrupted / failed', verified='Not confirmed')
            self.live.stop()
