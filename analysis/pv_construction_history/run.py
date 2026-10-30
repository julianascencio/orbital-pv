"""Two-date inventory matching; default is an explicitly synthetic split/expansion scenario."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from orbitalpv.ground_research import load_pv_inventory, match_pv_changes


def synthetic_inventory(boxes: list[tuple]) -> dict:
    """Small invented rectangles, not observed installations or dates."""
    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "synthetic algorithm demonstration",
            "license": "CC0",
            "observed": False,
        },
        "features": [
            {
                "type": "Feature",
                "id": str(i),
                "properties": {"synthetic": True},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                },
            }
            for i, (w, s, e, n) in enumerate(boxes)
        ],
    }


def run(
    output: Path,
    *,
    before: Path | None = None,
    after: Path | None = None,
    before_time: str = "2024-01-01",
    after_time: str = "2025-01-01",
    complete_coverage: bool = False,
) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Choose an empty analysis output directory")
    if (before is None) != (after is None):
        raise ValueError("Supply both dated inventories or neither for the synthetic scenario")
    if before is None:
        old = synthetic_inventory([(0, 0, 0.02, 0.01), (1, 1, 1.01, 1.01)])
        new = synthetic_inventory([(0, 0, 0.01, 0.01), (0.01, 0, 0.025, 0.01), (2, 2, 2.01, 2.01)])
        source = {
            "data_kind": "synthetic scenario; not real construction evidence",
            "purpose": "verify splitting, expansion, disappearance, addition and temporal ambiguity",
        }
    else:
        assert after is not None
        old, new = load_pv_inventory(before), load_pv_inventory(after)
        source = {
            "data_kind": "caller-provided dated inventories",
            "before_sha256": hashlib.sha256(before.read_bytes()).hexdigest(),
            "after_sha256": hashlib.sha256(after.read_bytes()).hexdigest(),
        }
    report = match_pv_changes(
        old,
        new,
        before_time=before_time,
        after_time=after_time,
        complete_coverage=complete_coverage,
    )
    report.update(source)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("before.geojson", old), ("after.geojson", new), ("report.json", report)):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/pv_construction_history"))
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--before-time", default="2024-01-01")
    parser.add_argument("--after-time", default="2025-01-01")
    parser.add_argument(
        "--complete-coverage",
        action="store_true",
        help="Assert BOTH dates comprehensively survey the same footprint",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.output,
                before=args.before,
                after=args.after,
                before_time=args.before_time,
                after_time=args.after_time,
                complete_coverage=args.complete_coverage,
            ),
            indent=2,
        )
    )
