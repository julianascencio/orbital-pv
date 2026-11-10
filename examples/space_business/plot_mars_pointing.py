"""
Mars orbital solar-array pointing reserve
========================================

NASA's November 9, 2026 ESCAPADE flyby update motivates a Mars mission power
planning screen. Can an assumed 1.4 kW array (at 1 AU) support a 300 W bus,
20% reserve and 30 degree off-pointing throughout a two-year Mars campaign?
NASA Mars24 seasonal distances and every power result are modeled. Array,
retention, load and conversion inputs are illustrative, not ESCAPADE specs.
"""

import json
from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from orbitalpv import ASTRONOMICAL_UNIT_M
from orbitalpv.environment import am0_irradiance
from orbitalpv.mars import mars_solar_parameters
from orbitalpv.physics import pointing_power_envelope


def configuration() -> dict:
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    return json.loads((directory / "_data/mars_pointing.json").read_text())


def study() -> tuple[pd.DataFrame, pd.DataFrame]:
    config = configuration()
    # These are TT calendar labels, deliberately not UTC timestamps.
    dates = pd.date_range(config["start_tt"], config["stop_tt"], freq="D")
    distance = mars_solar_parameters(dates.to_julian_date().to_numpy())["sun_distance_au"]
    flux = am0_irradiance(distance * ASTRONOMICAL_UNIT_M)
    relative_flux = flux / am0_irradiance(ASTRONOMICAL_UNIT_M)
    normal = config["array_1au_w"] * config["retention"] * config["bus_efficiency"]
    frame = pointing_power_envelope(
        normal * relative_flux,
        config["load_w"],
        reserve_fraction=config["reserve_fraction"],
        offpoint_deg=config["offpoint_deg"],
    )
    frame["date_tt"] = dates
    frame["sun_distance_au"] = distance
    frame["am0_w_m2"] = flux
    frame["fixed_1au_offpoint_bus_w"] = normal * np.cos(np.deg2rad(config["offpoint_deg"]))
    frame["fixed_mars_offpoint_bus_w"] = frame.fixed_1au_offpoint_bus_w / 1.52367934**2
    frame["required_array_1au_w"] = frame.required_bus_w / (
        relative_flux
        * config["retention"]
        * config["bus_efficiency"]
        * np.cos(np.deg2rad(config["offpoint_deg"]))
    )
    rows = []
    for rating, retention, load in product(
        config["sensitivity_array_1au_w"],
        config["sensitivity_retention"],
        config["sensitivity_load_w"],
    ):
        case = pointing_power_envelope(
            rating * retention * config["bus_efficiency"] * relative_flux,
            load,
            reserve_fraction=config["reserve_fraction"],
            offpoint_deg=config["offpoint_deg"],
        )
        rows.append(
            {
                "array_1au_w": rating,
                "retention": retention,
                "load_w": load,
                "minimum_headroom_w": float(case.headroom_w.min()),
                "normal_infeasible_samples": int((~case.normal_feasible).sum()),
                "offpoint_infeasible_samples": int((~case.offpoint_feasible).sum()),
                "samples": len(case),
                "passes_every_sample": bool(case.offpoint_feasible.all()),
            }
        )
    return frame, pd.DataFrame(rows)


def metrics(frame: pd.DataFrame, sensitivity: pd.DataFrame) -> dict:
    config = configuration()
    worst = frame.loc[frame.headroom_w.idxmin()]
    required = float(frame.required_array_1au_w.max())
    return {
        "data_kind": "NASA Mars24 modeled geometry; assumed engineering inputs",
        "samples": len(frame),
        "distance_min_au": float(frame.sun_distance_au.min()),
        "distance_max_au": float(frame.sun_distance_au.max()),
        "worst_date_tt": str(worst.date_tt.date()),
        "minimum_headroom_w": float(worst.headroom_w),
        "minimum_max_offpoint_deg": float(frame.max_offpoint_deg.min()),
        "offpoint_infeasible_samples": int((~frame.offpoint_feasible).sum()),
        "required_array_1au_w": required,
        "required_rating_increase_percent": 100 * (required / config["array_1au_w"] - 1),
        "required_rating_distance_stress_w": required
        * (1 + config["distance_stress_fraction"]) ** 2,
        "fixed_mars_headroom_w": float(worst.fixed_mars_offpoint_bus_w - worst.required_bus_w),
        "fixed_1au_headroom_w": float(worst.fixed_1au_offpoint_bus_w - worst.required_bus_w),
        "sensitivity_cases": len(sensitivity),
        "sensitivity_cases_passing_every_sample": int(sensitivity.passes_every_sample.sum()),
    }


def plot_results(frame: pd.DataFrame, sensitivity: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    axes[0].plot(frame.date_tt, frame.offpoint_bus_w, label="Mars model, 30°")
    axes[0].plot(
        frame.date_tt, frame.fixed_mars_offpoint_bus_w, "--", label="Fixed 1.52368 AU baseline"
    )
    axes[0].axhline(
        frame.required_bus_w.iloc[0], color="black", linestyle=":", label="Load + reserve"
    )
    axes[0].set(ylabel="Bus power (W)", title="Distance reduces usable power")
    axes[0].legend(fontsize=8)
    axes[1].plot(frame.date_tt, frame.max_offpoint_deg)
    axes[1].axhline(30, color="black", linestyle=":")
    axes[1].set(ylabel="Maximum array off-pointing (degrees)", title="Sunlit reserve constraint")
    for ax in axes[:2]:
        ax.tick_params(axis="x", rotation=35)
        ax.set_xlabel("Calendar date (TT)")
    selected = sensitivity[sensitivity.load_w == 300]
    for retention, group in selected.groupby("retention"):
        axes[2].plot(
            group.array_1au_w, group.minimum_headroom_w, "o-", label=f"Retention {retention:.0%}"
        )
    axes[2].axhline(0, color="black", linestyle=":")
    axes[2].set(
        xlabel="Array rating at 1 AU (W)",
        ylabel="Worst sampled headroom (W)",
        title="Assumed 300 W load, 30°",
    )
    axes[2].legend(fontsize=8)
    fig.suptitle("Mars seasonal planning screen — not ESCAPADE flight performance")
    return fig


if __name__ == "__main__":
    frame, sensitivity = study()
    print(json.dumps(metrics(frame, sensitivity), indent=2))
    plot_results(frame, sensitivity)
    plt.show()
