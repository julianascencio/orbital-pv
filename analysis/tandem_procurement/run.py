"""Reproduce the news-inspired HJT/tandem procurement decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from space_pv_analytics.procurement import ArrayOffer, break_even_cost_m2, size_array
from space_pv_connectors.procurement import load_array_offers

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "examples/space_business/_data"


def run(output: Path) -> dict:
    inputs = DATA / "array_offers.csv"
    frame = load_array_offers(inputs)
    offers = [
        ArrayOffer(**row)
        for row in frame[["name", "bol_w_m2", "eol_retention", "kg_m2", "cost_m2"]].to_dict(
            "records"
        )
    ]
    baseline, candidate = offers
    results = [
        {"name": offer.name, **asdict(size_array(offer, 10_000, launch_cost_kg=5000))}
        for offer in offers
    ]
    sweep = []
    for launch in (0, 1000, 5000, 10_000):
        for retention in np.linspace(0.55, 1.0, 46):
            altered = replace(candidate, eol_retention=float(retention))
            ceiling = break_even_cost_m2(baseline, altered, launch_cost_kg=launch)
            sweep.append(
                {
                    "launch_usd_kg": launch,
                    "tandem_retention": float(retention),
                    "break_even_usd_m2": ceiling,
                    "premium_over_baseline_fraction": ceiling / baseline.cost_m2 - 1,
                }
            )
    summary = {
        "evidence_status": "modeled scenario; not flight telemetry or a supplier quote",
        "source": json.loads((DATA / "provenance.json").read_text()),
        "inputs_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
        "required_sunlit_bus_w": 10_000,
        "margin": 0.2,
        "bus_efficiency": 0.9,
        "launch_usd_kg": 5000,
        "results": results,
        "candidate_break_even_usd_m2": break_even_cost_m2(baseline, candidate, launch_cost_kg=5000),
        "candidate_savings_usd": float(results[0]["total_cost"]) - float(results[1]["total_cost"]),
        "interpretation": "Conditional price ceiling only. Equal array-level gain, mass and five-year retention require qualification evidence. No continuous payload-power or investment-return claim.",
    }
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(output / "sizing.csv", index=False)
    pd.DataFrame(sweep).to_csv(output / "sensitivity.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/tandem_procurement"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
