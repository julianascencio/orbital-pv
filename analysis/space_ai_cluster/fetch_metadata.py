"""Optionally refresh exact-version bibliographic metadata; not needed to run."""

import argparse
from pathlib import Path

from orbitalpv.data import ArxivConnector

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("outputs/space_ai_cluster/arxiv-v2.xml"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    with ArxivConnector() as connector:
        result = connector.paper("2511.19468v2", cache_path=args.cache, refresh=args.refresh)
    print(result.data)
    print(f"Original response SHA-256: {result.receipt.sha256}")
