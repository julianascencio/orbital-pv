"""
Planning perovskite flight monitoring
=====================================

JAXA's October 30, 2026 update reports bus power delivery on September 10 and
plans further I-V monitoring. It publishes no numerical I-V series. This example
therefore models a campaign decision, **not OrigamiSat-2 performance**: can weekly
or daily matched sweeps detect a 5% annual loss with 80% probability using a 95%
two-sided interval? Noise and drift below are analyst assumptions.

The baseline assumes independent 2% log-power noise. Sensitivities add 3%
correlated log noise with a seven-day time scale and bounded ±0.01/year log
calibration drift. Daily sweeps consume more acquisition/downlink opportunities;
longer monitoring can be more valuable than denser sampling. Only valid,
normalized MPP observations count. See the analysis README for the equations,
source dates, limitations and reproduction commands.
"""

from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from orbitalpv.analytics import design_degradation_monitoring, log_power_covariance
from orbitalpv.data import load_table


def campaign_table() -> pd.DataFrame:
    """Evaluate 30 duration/cadence/noise combinations from a local input table."""
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    cases = load_table(directory / "_data/monitoring_noise_cases.csv")
    rows = []
    for case in cases.to_dict("records"):
        for cadence in (1, 7):
            for duration in (28, 91, 182, 364, 728):
                times = np.arange(0, duration + 1, cadence, dtype=float)
                covariance = log_power_covariance(
                    times,
                    independent_sigma=float(case["independent_sigma"]),
                    correlated_sigma=float(case["correlated_sigma"]),
                    correlation_days=float(case["correlation_days"]),
                )
                design = design_degradation_monitoring(
                    times, covariance, drift_bound_per_year=float(case["drift_bound_per_year"])
                )
                rows.append(
                    {
                        "scenario": case["scenario"],
                        "cadence_days": cadence,
                        **asdict(design),
                        "detects_five_percent_annual_loss": design.minimum_detectable_annual_loss
                        <= 0.05,
                    }
                )
    return pd.DataFrame(rows)


def plot_campaign(results: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for axis, cadence in zip(axes, (1, 7), strict=True):
        subset = results[results.cadence_days == cadence]
        for name, group in subset.groupby("scenario", sort=False):
            axis.plot(
                group.duration_days,
                group.minimum_detectable_annual_loss * 100,
                "o-",
                label=str(name).replace("_", " "),
            )
        axis.axhline(5, color="black", linestyle="--", label="5% annual-loss target")
        axis.set(title=f"One valid sweep every {cadence} day(s)", xlabel="Campaign duration (days)")
        axis.set_yscale("log")
        axis.grid(alpha=0.3)
    axes[0].set_ylabel("Minimum detectable annual loss (%)")
    axes[1].legend(fontsize=8)
    fig.suptitle("Modeled campaign sensitivity: 95% interval, 80% detection probability")
    fig.tight_layout()
    return fig


if __name__ == "__main__":
    results = campaign_table()
    print(results.to_string(index=False))
    plot_campaign(results)
    plt.show()
