"""
Repaired panel power: accept or measure again?
============================================================

ESA's November 5, 2026 Da Vinci report motivates electrical acceptance after
panel damage. ESA publishes no numerical power data. All eight paired Pmax
readings and uncertainty budgets here are **synthetic assumptions**, not Da
Vinci measurements. A bound below the assumed 95% retention requirement means
insufficient evidence, not a failed panel. Flight qualification is separate.
"""

from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from orbitalpv.acceptance import plan_power_retention_test, power_retention_acceptance
from orbitalpv.data import load_table

CONFIG = {
    "repeat_log_sigma": 0.01,
    "before_calibration_log_sigma": 0.02,
    "after_calibration_log_sigma": 0.02,
    "minimum_retention": 0.95,
    "confidence": 0.95,
}


def study() -> tuple[pd.DataFrame, pd.DataFrame]:
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    pairs = load_table(directory / "_data/panel_acceptance.csv")
    cases = []
    for rho in (0.0, 0.5, 0.9, 1.0):
        result = power_retention_acceptance(
            pairs.before_power_w,
            pairs.after_power_w,
            calibration_correlation=rho,
            **CONFIG,
        )
        cases.append({"calibration_correlation": rho, **asdict(result)})
    plans = []
    for rho in (0.0, 0.5, 0.9, 1.0):
        for n in (1, 2, 4, 8, 16, 32, 64, 128):
            result = plan_power_retention_test(
                cases[0]["retention"], n, calibration_correlation=rho, **CONFIG
            )
            plans.append({"calibration_correlation": rho, **asdict(result)})
    return pd.DataFrame(cases), pd.DataFrame(plans)


def plot_study(cases: pd.DataFrame, plans: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    rho = cases.calibration_correlation
    axes[0].plot(rho, 100 * cases.retention, "o--", label="Point estimate only")
    axes[0].plot(rho, 100 * cases.lower_retention, "o-", label="95% one-sided lower bound")
    axes[0].axhline(95, color="black", linestyle=":", label="Assumed requirement")
    axes[0].set(xlabel="Before/after calibration correlation", ylabel="Power retention (%)")
    axes[0].legend(fontsize=8)
    for correlation, group in plans.groupby("calibration_correlation"):
        axes[1].plot(
            group.observations, 100 * group.lower_retention, "o-", label=f"rho={correlation:g}"
        )
    axes[1].axhline(95, color="black", linestyle=":")
    axes[1].set(
        xlabel="Independent paired repeats (planned)",
        ylabel="Lower bound at fixed point estimate (%)",
        xscale="log",
    )
    axes[1].legend(fontsize=8)
    fig.suptitle("Synthetic panel acceptance — calibration uncertainty does not average away")
    return fig


if __name__ == "__main__":
    cases, plans = study()
    print(cases.to_string(index=False))
    plot_study(cases, plans)
    plt.show()
