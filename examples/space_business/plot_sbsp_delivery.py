"""
Space solar delivery versus firm power
======================================

A September 30, 2026 supplier announcement describes a proposed 100 MW,
876,000 MWh/year supply. This backlog case screens a datacenter's backup needs:
annual surplus cannot cancel power interruptions. The source values are advertised
contract targets; the hourly profiles and efficiencies here are constructed
scenarios, not measured satellite or receiver performance.
"""

from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.delivery import assess_delivery, delivery_chain


def study() -> pd.DataFrame:
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    cases = load_table(directory / "_data/sbsp_delivery.csv").to_dict("records")
    for power in (160, 200, 250, 300):
        for capture in (0.6, 0.8, 1.0):
            cases.append(
                dict(
                    name=f"pv_{power}_capture_{capture}",
                    pv_dc_mw=power,
                    conditioning=0.95,
                    dc_rf=0.7,
                    capture=capture,
                    rf_dc=0.85,
                    grid=0.98,
                    outage_hours=88,
                )
            )
    rows = []
    for case in cases:
        for pattern in ("clustered", "distributed"):
            pv = np.full(8760, float(case["pv_dc_mw"]) * 1e6)
            n = int(case["outage_hours"])
            indices = np.arange(n) if pattern == "clustered" else np.arange(n) * 99
            pv[indices] = 0
            chain = delivery_chain(
                pv,
                {k: float(case[k]) for k in ("conditioning", "dc_rf", "capture", "rf_dc", "grid")},
            )
            result = assess_delivery(
                np.arange(8761), chain["grid"], 100e6, energy_target_wh=876000e6, tolerance_w=1e-6
            )
            rows.append({"scenario": case["name"], "pattern": pattern, **asdict(result)})
    return pd.DataFrame(rows)


def plot_results(results: pd.DataFrame) -> plt.Figure:
    selected = results[results.scenario == "energy_surplus_interrupted"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    row = selected.iloc[0]
    axes[0].bar(
        ["Annual target", "Delivered", "Served load"],
        [876000, row.delivered_wh / 1e6, row.served_wh / 1e6],
    )
    axes[0].set(ylabel="Energy (MWh)", title="Surplus does not cover interruptions")
    axes[1].bar(selected.pattern, selected.largest_event_shortfall_wh / 1e9)
    axes[1].set(ylabel="Largest event deficit (GWh)", title="Same energy, different backup burden")
    fig.suptitle("Constructed SBSP delivery scenarios — not flight measurements")
    return fig


if __name__ == "__main__":
    results = study()
    print(results.to_string(index=False))
    plot_results(results)
    plt.show()
