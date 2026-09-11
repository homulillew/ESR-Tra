"""Build a new CPU retrieval index from the complete legal local corpus."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from esr_harness.local_retrieval import build_index

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(build_index(a.corpus, a.output))
