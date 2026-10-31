"""Plot measured CSV: python -m scripts.plot_results --output results/phase2."""
import argparse
from bionet.benchmark import plot
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='results/phase2')
    plot(parser.parse_args().output)
