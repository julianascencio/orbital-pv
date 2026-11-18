"""
CME forecast disagreement and PV telemetry budgets
=====================================================================

NASA CCMC research forecasts submitted November 15 for the November 14, 2026
CME are imported facts, not verified arrivals. Missing SARM bounds are assigned
explicit 6/12/24-hour planning buffers. No storm probability or PV loss is
inferred. Official operational forecasts come from NOAA SWPC, not this study.
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.monitoring_windows import forecast_monitoring_windows, monitoring_sample_budget

AS_OF = "2026-11-16T10:00:00Z"


def study():
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    forecasts = load_table(directory / "_data/cme_arrival_forecasts.csv")
    mean_arrival = pd.to_datetime(forecasts.arrival_utc, utc=True).mean()
    baseline = pd.DataFrame(
        [
            {
                "method": "computed midpoint",
                "submitted_utc": AS_OF,
                "arrival_utc": mean_arrival,
                "before_hours": 7,
                "after_hours": 7,
            }
        ]
    )
    windows, rows = {}, []
    for policy, data, padding in [
        ("midpoint ±7h", baseline, None),
        ("union: missing ±6h", forecasts, 6),
        ("union: missing ±12h", forecasts, 12),
        ("union: missing ±24h", forecasts, 24),
    ]:
        union, _ = forecast_monitoring_windows(data, as_of_utc=AS_OF, missing_bound_hours=padding)
        windows[policy] = union
        for cadence in (60, 600):
            rows.append(
                {
                    "policy": policy,
                    "cadence_s": cadence,
                    **monitoring_sample_budget(union, cadence_s=cadence, bytes_per_sample=256),
                }
            )
    return pd.DataFrame(rows), windows


def plot_study(results, windows):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for i, (_policy, frame) in enumerate(windows.items()):
        for row in frame.itertuples():
            axes[0].plot(
                [row.start_utc, row.end_utc],
                [i, i],
                linewidth=8,
                solid_capstyle="butt",
                color=f"C{i}",
            )
    axes[0].set_yticks(range(len(windows)), list(windows))
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M", tz="UTC"))
    axes[0].set(xlabel="UTC in November 2026", title="Forecast windows plus assumed buffers")
    for cadence, group in results.groupby("cadence_s"):
        axes[1].plot(range(len(group)), group["bytes"] / 1e6, "o-", label=f"{cadence}s cadence")
    axes[1].set_xticks(range(len(windows)), ["midpoint", "±6h", "±12h", "±24h"])
    axes[1].set(ylabel="Telemetry MB (decimal)", title="Assumed 256 bytes per sample")
    axes[1].legend()
    return fig


if __name__ == "__main__":
    results, windows = study()
    print(results.to_string(index=False))
    plot_study(results, windows)
    plt.show()
