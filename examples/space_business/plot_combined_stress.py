"""
Do separate stress tests miss combined power loss?
======================================================================

DOE's June 2, 2026 workshop motivates the existing combined-stressor backlog.
All sample powers below are synthetic, not DOE measurements. Four randomized
arms compare control, radiation, thermal and a declared combined protocol.
Bootstrap bounds are approximate and do not establish flight qualification.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.stress import combined_stress_interaction


def study():
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    samples = load_table(directory / "_data/combined_stress.csv")
    result, arms = combined_stress_interaction(samples, seed=1711)
    rows = []
    for combined_retention in (0.84, 0.90, 0.931 / 0.995, 0.97):
        scenario = samples.copy()
        mask = scenario.arm == "combined"
        scenario.loc[mask, "after_power_w"] *= combined_retention / 0.84
        metrics, _ = combined_stress_interaction(scenario, seed=1711)
        rows.append({"assumed_combined_retention": combined_retention, **metrics})
    return result, arms, pd.DataFrame(rows)


def plot_study(result, arms, sensitivity):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    axes[0].bar(arms.arm, 100 * arms.geometric_retention)
    axes[0].axhline(
        100 * result["independent_retention"],
        color="black",
        linestyle="--",
        label="Independent-stress baseline",
    )
    axes[0].set(ylabel="Geometric retained Pmax (%)", ylim=(0, 105))
    axes[0].legend(fontsize=8)
    axes[1].errorbar(
        100 * sensitivity.assumed_combined_retention,
        sensitivity.interaction_ratio,
        yerr=[
            sensitivity.interaction_ratio - sensitivity.ratio_lower,
            sensitivity.ratio_upper - sensitivity.interaction_ratio,
        ],
        fmt="o",
        capsize=4,
    )
    axes[1].axhline(1, color="black", linestyle="--")
    axes[1].set(
        xlabel="Assumed combined retention (%)",
        ylabel="Combined / independent retention",
        title="95% percentile bootstrap bounds",
    )
    fig.suptitle("Synthetic combined-stress evidence — no flight or DOE measurement data")
    return fig


if __name__ == "__main__":
    result, arms, sensitivity = study()
    print(result)
    print(sensitivity.to_string(index=False))
    plot_study(result, arms, sensitivity)
    plt.show()
