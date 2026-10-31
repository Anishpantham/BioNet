"""Run from repository root: python -m scripts.run_experiments [benchmark options]."""
import sys
from bionet.cli import main
if __name__ == '__main__':
    sys.argv.insert(1, 'benchmark')
    main()
