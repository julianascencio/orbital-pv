"""Compose reproducible array I-V fault scenarios using the public physics API."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv import physics as opv


def run(output: Path) -> dict:
    healthy = opv.PVSubstring(5.0, 20.0, diode_voltage_v=0.8, series_resistance_ohm=0.05)
    shaded = replace(healthy, photocurrent_a=1.5, open_circuit_voltage_v=19.0)
    scenarios = {
        "healthy": [[healthy] * 3, [healthy] * 3],
        "one_shaded_substring": [[healthy, healthy, shaded], [healthy] * 3],
        "one_bypassed_open_substring": [
            [healthy, healthy, replace(healthy, fault="open")],
            [healthy] * 3,
        ],
        "one_unbypassed_open_string": [
            [healthy, healthy, replace(healthy, fault="open", bypass_voltage_v=None)],
            [healthy] * 3,
        ],
        "one_shorted_substring": [
            [healthy, healthy, replace(healthy, fault="short")],
            [healthy] * 3,
        ],
    }
    voltage = np.linspace(0, 60, 1201)
    records = []
    curves = []
    for label, strings in scenarios.items():
        curve = opv.array_iv_curve(strings, voltage)
        records.append(
            {"case": label, **{key: curve.attrs[key] for key in ("pmp_w", "vmp_v", "imp_a")}}
        )
        curve["case"] = label
        curves.append(curve)
    summary = {
        "input_kind": "synthetic circuit scenarios, not labeled spacecraft faults",
        "substring": asdict(healthy),
        "mpp": records,
        "interpretation": "Constant-drop bypass and ideal blocking diodes; no reverse breakdown, hot spots, or arcing.",
        "inspiration_doi": "10.1016/j.ast.2026.112139",
    }
    output.mkdir(parents=True, exist_ok=True)
    pd.concat(curves).to_csv(output / "iv_curves.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/array_fault_signatures"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
