"""Local-only Apple Silicon validation. Never opens the real biometric dataset.

Install with python3.12 -m pip install -e '.[dev]', then run:
python3.12 -m scripts.validate_macos --output results/macos-local
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='results/macos-local')
    parser.add_argument('--gib', action='store_true', help='also profile a 1 GiB synthetic file')
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        parser.error('run on Apple Silicon macOS; this script cannot certify another platform')
    if sys.version_info < (3, 12): parser.error('Python 3.12+ required')
    root = Path(args.output).resolve(); root.mkdir(parents=True, exist_ok=False)
    (root/'environment.json').write_text(json.dumps(dict(python=sys.version,
        platform=platform.platform(), machine=platform.machine()), indent=2)+'\n')
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', NO_COLOR='1',
               MPLCONFIGDIR=str(root/'matplotlib-cache'))
    commands = [
        ('tests', [sys.executable,'-m','pytest','-q','-ra','--junitxml='+str(root/'tests.xml')], 300),
        ('benchmark', [sys.executable,'-m','bionet','benchmark','--output',str(root/'benchmark'),
            '--sizes','16384','65536','--windows','8','32','--losses','0','.1','.4','--trials','3'], 900),
        ('profile', [sys.executable,'-m','scripts.phase3_profile','--output',str(root/'profile'),
            '--sizes','1','10','100']+(['1024'] if args.gib else []), 1200),
    ]
    statuses = []
    for name, command, timeout in commands:
        print('Running', name, flush=True)
        with (root/(name+'.log')).open('w') as log:
            try:
                completed = subprocess.run(command, stdout=log, stderr=log, env=env, timeout=timeout)
                statuses.append(dict(name=name, command=command, returncode=completed.returncode))
            except subprocess.TimeoutExpired:
                statuses.append(dict(name=name, command=command, error='timeout'))
        (root/'commands.json').write_text(json.dumps(statuses, indent=2)+'\n')
    if any(s.get('returncode') != 0 for s in statuses):
        raise SystemExit('Validation failed; inspect '+str(root))
    print('Automated synthetic validation passed. Still rehearse dashboard in Terminal and test a trusted LAN.')


if __name__ == '__main__': main()
