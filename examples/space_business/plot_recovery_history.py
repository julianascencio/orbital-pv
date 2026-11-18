"""
Sizing power margin without assuming guaranteed recovery
========================================================

P8.7 recovery-aware degradation: hypothetical rates and exposure history.
The October 15, 2026 electron-irradiation paper motivates recovery testing,
not these numerical coefficients. No measured or mission performance implied.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.recovery import recovery_history


def study():
    root = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    history = load_table(root / "_data/recovery_history.csv")
    traces, metrics = [], []
    for factor in (0.0, 0.25, 0.5, 1.0, 2.0):
        scenario = history.copy()
        scenario["recovery_rate_h_inv"] *= factor
        trace = recovery_history(scenario, permanent_retention=0.98)
        trace["recovery_multiplier"] = factor
        traces.append(trace)
        worst = trace.minimum_retention.min()
        metrics.append(
            {
                "recovery_multiplier": factor,
                "minimum_retention": worst,
                "final_retention": trace.end_retention.iloc[-1],
                "mean_retention": (trace.mean_retention * trace.duration_h).sum() / 20,
                "required_bol_w": 1000 / worst,
            }
        )
    return pd.concat(traces, ignore_index=True), pd.DataFrame(metrics)


def plot_study(traces, metrics):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for factor, group in traces.groupby("recovery_multiplier"):
        # Endpoints only: straight segments are visual guides, not the ODE solution.
        axes[0].plot([0, *group.end_h], [0.98, *group.end_retention], "o--", label=str(factor))
    axes[0].set(
        xlabel="Elapsed scenario time (h)",
        ylabel="Power retention",
        title="Interval endpoints (guides between points)",
    )
    axes[0].legend(title="Recovery multiplier")
    axes[1].plot(metrics.recovery_multiplier, metrics.required_bol_w, "o-")
    axes[1].set(
        xlabel="Assumed recovery multiplier",
        ylabel="Required BOL power (W)",
        title="Maintain 1,000 W at worst retention",
    )
    fig.suptitle("Hypothetical kinetics — no measured performance")
    return fig


if __name__ == "__main__":
    traces, metrics = study()
    print(metrics.to_string(index=False))
    plot_study(traces, metrics)
    plt.show()
