"""
Scheduling lunar rover charging against solar power
======================================================================

NASA's November 7, 2026 miniCAST announcement motivates this synthetic study.
All tower ratings, receiver loads and windows are assumptions, not NASA design
values. Charging is constant-power and noninterruptible on an hourly grid.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from orbitalpv.charging import schedule_charging
from orbitalpv.data import load_table
from orbitalpv.physics import BatterySpec, dispatch_power


def study():
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    requests = load_table(directory / "_data/lunar_charging.csv")
    rows, traces, schedules = [], {}, {}
    for efficiency in (0.6, 0.8, 1.0):
        for pv_w in (500, 700, 900):
            generation = np.full(6, pv_w, dtype=float)
            base = np.full(6, 100.0)
            schedule, trace = schedule_charging(
                generation, base, requests, slot_hours=1, efficiency=efficiency
            )
            earliest = base.copy()
            for row in requests.to_dict("records"):
                start = row["release_slot"]
                earliest[start : start + row["duration_slots"]] += (
                    row["delivered_power_w"] / efficiency
                )
            for policy, load in [("earliest", earliest), ("scheduled", trace.load_w.to_numpy())]:
                dispatch = dispatch_power(
                    np.arange(7) * 3600,
                    generation,
                    load,
                    battery=BatterySpec(
                        2000,
                        initial_soc=0.8,
                        minimum_soc=0.2,
                        max_charge_w=500,
                        max_discharge_w=1000,
                    ),
                )
                rows.append(
                    {
                        "efficiency": efficiency,
                        "pv_w": pv_w,
                        "policy": policy,
                        "peak_bus_w": float(load.max()),
                        "peak_deficit_w": float(np.maximum(load - generation, 0).max()),
                        "requested_receiver_wh": float(
                            (requests.delivered_power_w * requests.duration_slots).sum()
                        ),
                        "unserved_bus_wh": float(
                            (dispatch.unserved_load_w * dispatch.duration_h).sum()
                        ),
                        "final_soc": float(dispatch.soc_end.iloc[-1]),
                    }
                )
                if efficiency == 0.8 and pv_w == 700:
                    traces[policy] = load
                    schedules[policy] = schedule if policy == "scheduled" else requests
    return pd.DataFrame(rows), traces, schedules


def plot_study(results, traces):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for policy, load in traces.items():
        axes[0].stairs(load, np.arange(7), label=policy)
    axes[0].axhline(700, color="black", linestyle="--", label="Assumed solar supply")
    axes[0].set(
        xlabel="Elapsed hours", ylabel="Requested tower bus W", title="80% delivery efficiency"
    )
    axes[0].legend()
    for policy, group in results[results.pv_w == 700].groupby("policy"):
        axes[1].plot(group.efficiency, group.unserved_bus_wh, "o-", label=policy)
    axes[1].set(
        xlabel="Assumed delivery efficiency",
        ylabel="Unserved bus Wh",
        title="Finite battery dispatch check",
    )
    axes[1].legend()
    fig.suptitle("Synthetic miniCAST-inspired charging study — not mission performance")
    return fig


if __name__ == "__main__":
    results, traces, schedules = study()
    print(results.to_string(index=False))
    plot_study(results, traces)
    plt.show()
