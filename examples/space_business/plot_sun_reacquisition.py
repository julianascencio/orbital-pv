"""
Battery reserve for delayed Sun reacquisition
=============================================

NASA's November 19, 2026 Odyssey report motivates a finite-horizon power
contingency screen. Compare maintaining normal load with shedding discretionary
load while awaiting restored array pointing. Engineering inputs are synthetic,
not Odyssey specifications or telemetry. A backward reserve envelope is checked
against forward energy-conserving dispatch, including a terminal SOC target.
"""

import json
from dataclasses import replace
from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.physics import (
    BatterySpec,
    InfeasibleReserveError,
    battery_reserve_envelope,
    dispatch_power,
)


def inputs():
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    config = json.loads((directory / "_data/sun_reacquisition.json").read_text())
    return config, load_table(directory / "_data/sun_reacquisition.csv")


def profile(config, phases, delay_h, delay_load_w, generation_scale):
    duration = phases.duration_h.to_numpy()
    generation = phases.generation_w.to_numpy() * generation_scale
    demand = phases.demand_w.to_numpy()
    if delay_h > 0:
        duration = np.r_[delay_h, duration]
        generation = np.r_[config["delay_generation_w"] * generation_scale, generation]
        demand = np.r_[delay_load_w, demand]
    return np.r_[0, np.cumsum(duration) * 3600], generation, demand


def study():
    config, phases = inputs()
    base = BatterySpec(**config["battery"])
    rows = []
    for capacity, scale, (policy, load), delay in product(
        config["capacity_sensitivity_wh"],
        config["generation_sensitivity_scale"],
        config["delay_loads_w"].items(),
        config["delays_h"],
    ):
        battery = replace(base, capacity_wh=capacity)
        times, generation, demand = profile(config, phases, delay, load, scale)
        trace = dispatch_power(times, generation, demand, battery=battery)
        unmet = float((trace.unserved_load_w * trace.duration_h).sum())
        final = float(trace.soc_end.iloc[-1])
        required_soc = None
        reason = ""
        try:
            envelope = battery_reserve_envelope(
                times, generation, demand, battery=battery, terminal_soc=config["terminal_soc"]
            )
            required_soc = float(envelope.required_soc.iloc[0])
        except InfeasibleReserveError as exc:
            reason = str(exc)
        feasible = required_soc is not None and required_soc <= battery.initial_soc + 1e-10
        forward_feasible = unmet <= 1e-7 and final >= config["terminal_soc"] - 1e-10
        if feasible != forward_feasible:
            raise AssertionError("Backward envelope and forward dispatch disagree")
        rows.append(
            dict(
                capacity_wh=capacity,
                generation_scale=scale,
                policy=policy,
                delay_h=delay,
                required_initial_soc=required_soc,
                infeasible_reason=reason,
                feasible=feasible,
                unserved_wh=unmet,
                final_soc=final,
            )
        )
    return pd.DataFrame(rows)


def metrics(results):
    base = results[(results.capacity_wh == 600) & (results.generation_scale == 1)]
    limits = {}
    for policy, group in base.groupby("policy"):
        passing = group[group.feasible]
        limit = float(passing.delay_h.max()) if len(passing) else None
        limits[policy] = {
            "latest_sampled_delay_h": limit,
            "sweep_upper_bound_reached": limit == float(group.delay_h.max()),
        }
    return {
        "data_kind": "synthetic engineering scenarios",
        "cases": len(results),
        "backward_forward_agreement": True,
        "baseline_delay_limits": limits,
    }


def plot_study(results):
    config, phases = inputs()
    battery = BatterySpec(**config["battery"])
    base = results[(results.capacity_wh == battery.capacity_wh) & (results.generation_scale == 1)]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    for policy, group in base.groupby("policy"):
        axes[0].plot(group.delay_h, group.required_initial_soc, "o-", label=policy)
    axes[0].axhline(battery.initial_soc, color="black", linestyle=":", label="Available SOC")
    axes[0].set(
        xlabel="Reacquisition delay (h)",
        ylabel="Minimum initial SOC",
        title="Gaps mean no allowed SOC suffices",
    )
    axes[0].legend(fontsize=8)
    times, generation, demand = profile(config, phases, 2, config["delay_loads_w"]["load_shed"], 1)
    envelope = battery_reserve_envelope(
        times, generation, demand, battery=battery, terminal_soc=config["terminal_soc"]
    )
    trace = dispatch_power(times, generation, demand, battery=battery)
    axes[1].plot(times / 3600, np.r_[battery.initial_soc, trace.soc_end], "o-", label="Forward SOC")
    axes[1].plot(times / 3600, envelope.required_soc, "o--", label="Required SOC")
    axes[1].set(xlabel="Elapsed time (h)", ylabel="SOC", title="2 h delay with load shedding")
    axes[1].legend(fontsize=8)
    for (capacity, policy), group in results.groupby(["capacity_wh", "policy"]):
        if policy != "load_shed":
            continue
        limits = group.groupby("generation_scale").apply(
            lambda g: g.loc[g.feasible, "delay_h"].max(), include_groups=False
        )
        axes[2].plot(limits.index, limits, "o-", label=f"{capacity:g} Wh")
    axes[2].set(
        xlabel="Assumed PV multiplier",
        ylabel="Latest passing sampled delay (h)",
        title="Load shedding sensitivity; grid 0.25 h",
    )
    axes[2].legend(fontsize=8)
    fig.suptitle("Synthetic contingency screen — not an Odyssey recovery forecast")
    return fig


if __name__ == "__main__":
    results = study()
    print(json.dumps(metrics(results), indent=2))
    plot_study(results)
    plt.show()
