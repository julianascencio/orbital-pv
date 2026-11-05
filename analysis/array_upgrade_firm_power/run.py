"""Reproduce the solar-array upgrade continuous-load screening case."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.physics import BatterySpec, dispatch_power, periodic_load_limit

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "examples/space_business/_data"


def run(output: Path) -> None:
    source = DATA / "array_upgrade_cases.csv"
    cases = load_table(source)
    rows = []
    for row in cases.to_dict("records"):
        battery = BatterySpec(
            capacity_wh=row["nominal_battery_wh"],
            initial_soc=0.2,
            minimum_soc=0.2,
            maximum_soc=0.9,
            max_charge_w=200000,
            max_discharge_w=200000,
        )
        limits = periodic_load_limit(row["sunlit_power_w"], 1, 35 / 60, battery=battery)
        trace = dispatch_power(
            [0, 3600, 5700, 9300, 11400],
            [row["sunlit_power_w"], 0, row["sunlit_power_w"], 0],
            limits["sustainable_load_w"],
            battery=battery,
        )
        rows.append(
            {
                "scenario": row["scenario"],
                **limits,
                "max_unserved_w": float(trace.unserved_load_w.max()),
                "final_soc": float(trace.soc_end.iloc[-1]),
            }
        )
    sweep = []
    for eclipse in (20, 35, 45):
        for pv in (160000, 215000):
            for capacity in np.linspace(40_000, 160_000, 61):
                battery = BatterySpec(
                    capacity_wh=float(capacity),
                    minimum_soc=0.2,
                    maximum_soc=0.9,
                    max_charge_w=200000,
                    max_discharge_w=200000,
                )
                sweep.append(
                    {
                        "eclipse_min": eclipse,
                        "pv_w": pv,
                        "battery_wh": capacity,
                        **periodic_load_limit(pv, 1, eclipse / 60, battery=battery),
                    }
                )
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "results.csv", index=False)
    pd.DataFrame(sweep).to_csv(output / "sensitivity.csv", index=False)
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "source": json.loads((DATA / "array_upgrade_provenance.json").read_text()),
                "inputs_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/array_upgrade_firm_power"))
    run(parser.parse_args().output)
