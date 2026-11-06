"""Reproduce the lunar utility service admission study."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.physics import BatterySpec
from orbitalpv.utility import screen_power_service

DATA = Path(__file__).resolve().parents[2] / "examples/space_business/_data"


def run(output: Path) -> None:
    path = DATA / "lunar_utility_cases.csv"
    results = []
    for row in load_table(path).to_dict("records"):
        battery = BatterySpec(
            float(row["battery_wh"]),
            initial_soc=0.9,
            minimum_soc=0.2,
            maximum_soc=0.95,
            max_charge_w=20000,
            max_discharge_w=20000,
        )
        result = screen_power_service(
            [0, row["dark_h"] * 3600, (row["dark_h"] + row["sun_h"]) * 3600],
            [0, row["pv_w"]],
            50,
            list(range(13)),
            customer_power_w=50,
            delivery_efficiency=0.9,
            battery=battery,
        )
        result.insert(0, "scenario", row["scenario"])
        results.append(result)
    output.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(results, ignore_index=True)
    combined.to_csv(output / "admission.csv", index=False)
    combined[combined.repeatable_profile_feasible].groupby("scenario").customers.max().to_csv(
        output / "customer_limits.csv"
    )
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "source": json.loads((DATA / "lunar_utility_provenance.json").read_text()),
                "inputs_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/lunar_utility_service"))
    run(parser.parse_args().output)
