import argparse
import json
from . import sender, receiver, tcp_baseline, benchmark

def main():
    parser = argparse.ArgumentParser(description='BioNet reliable file transmission')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('sender', 'receiver', 'tcp-sender', 'tcp-receiver'):
        p = sub.add_parser(name)
        p.add_argument('--host', default='127.0.0.1')
        p.add_argument('--port', type=int, default=9001 if name.startswith('tcp') else 9000)
        p.add_argument('--file', required=True) if name.endswith('sender') else p.add_argument('--output', default='received')
        if not name.startswith('tcp'):
            p.add_argument('--window-size', type=int, default=32)
            for option in ('loss', 'latency', 'jitter', 'reorder', 'corruption'):
                p.add_argument('--'+option, type=float, default=0)
            p.add_argument('--seed', type=int, default=1)
            if name == 'sender':
                p.add_argument('--timeout', type=float, default=.1)
                p.add_argument('--retries', type=int, default=50)
                p.add_argument('--chunk-size', type=int, default=1024)
                p.add_argument('--verbose', action='store_true')
            else:
                p.add_argument('--idle-timeout', type=float, default=30)
                p.add_argument('--max-size', type=int, default=1 << 40)
    p = sub.add_parser('benchmark'); p.add_argument('--output', default='results'); p.add_argument('--trials', type=int, default=3)
    args = vars(parser.parse_args()); command = args.pop('command')
    try:
        result = {'sender': sender.send, 'receiver': receiver.receive, 'tcp-sender': tcp_baseline.send, 'tcp-receiver': tcp_baseline.receive, 'benchmark': benchmark.run}[command](**args)
        if result is not None:
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'BioNet: {exc}\n')
