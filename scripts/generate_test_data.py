"""Generate a synthetic ZIP; never reads biometric data."""
import argparse
import random
import zipfile
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--output', default='data/synthetic.zip'); p.add_argument('--size', type=int, default=1048576)
a = p.parse_args(); path = Path(a.output); path.parent.mkdir(parents=True, exist_ok=True)
rng = random.Random(42)
with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as archive:
    with archive.open('synthetic.bin', 'w') as stream:
        for offset in range(0, a.size, 65536):
            stream.write(rng.randbytes(min(65536, a.size-offset)))
print(path)
