"""
Real BIRDS CubeSat solar-panel telemetry
========================================

This example walks step by step through a real on-orbit PV analysis using the
public ``orbitalpv`` API.

We use **RAAVANA**, one of the BIRDS 1U CubeSats. The public BIRDS EPS dataset
contains measured solar-panel voltage, current and temperature. The dataset
paper reports that RAAVANA experienced a panel failure during its mission,
which makes it useful for demonstrating health-oriented analysis.

Source
------

* Jara et al. (2022), *On-orbit Electrical Power System Dataset of 1U
  CubeSat constellation for Machine Learning Models*.
* DOI: 10.17632/8kp25ycf63.1
* Upstream repository: https://github.com/BIRDSOpenSource/EPS_dataset

The analysis below is exploratory. It demonstrates how to retrieve, normalize,
visualize and summarize the real telemetry; it does not claim to reproduce the
authors' expert fault labels or a flight-qualified diagnosis.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import orbitalpv as opv

# %% Step 1 — Download and normalize the real telemetry
#
# ``fetch_birds_eps`` downloads the original XLSX workbook and converts all
# recognizable panel telemetry into OrbitalPV's canonical schema.

cache = Path(gettempdir()) / "orbitalpv-real-data"
cache.mkdir(parents=True, exist_ok=True)
workbook = cache / "RAAVANA.xlsx"

telemetry = opv.fetch_birds_eps("RAAVANA", workbook)
telemetry = telemetry.dropna(subset=["timestamp", "voltage_v", "current_a"])
telemetry = telemetry.sort_values(["panel_id", "timestamp"]).reset_index(drop=True)

print(f"rows={len(telemetry):,}")
print(f"panels={telemetry['panel_id'].nunique()}")
print(f"start={telemetry['timestamp'].min()}")
print(f"end={telemetry['timestamp'].max()}")

counts = telemetry.groupby("panel_id").size().sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(8.5, 4.5))
counts.plot.bar(ax=ax)
ax.set(xlabel="Panel", ylabel="Telemetry samples")
ax.set_title("Step 1 — Real RAAVANA samples available by panel")
ax.grid(True, axis="y", alpha=0.3)
plt.show()

# %% Step 2 — Inspect measured panel voltage
#
# We lightly downsample only for plotting so the figure remains readable.
# The analysis itself continues to use every valid telemetry sample.

plot_parts = []
for _, panel in telemetry.groupby("panel_id", sort=True):
    stride = max(1, len(panel) // 2500)
    plot_parts.append(panel.iloc[::stride])
plot_frame = pd.concat(plot_parts, ignore_index=True)

fig, ax = plt.subplots(figsize=(10, 4.8))
for panel_id, panel in plot_frame.groupby("panel_id", sort=True):
    ax.plot(panel["timestamp"], panel["voltage_v"], ".", ms=2, alpha=0.55, label=panel_id)
ax.set(xlabel="UTC time", ylabel="Panel voltage [V]")
ax.set_title("Step 2 — Measured solar-panel voltage")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=7, ncols=2)
fig.autofmt_xdate()
plt.show()

# %% Step 3 — Inspect measured panel current

fig, ax = plt.subplots(figsize=(10, 4.8))
for panel_id, panel in plot_frame.groupby("panel_id", sort=True):
    ax.plot(panel["timestamp"], panel["current_a"], ".", ms=2, alpha=0.55, label=panel_id)
ax.set(xlabel="UTC time", ylabel="Panel current [A]")
ax.set_title("Step 3 — Measured solar-panel current")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=7, ncols=2)
fig.autofmt_xdate()
plt.show()

# %% Step 4 — Convert voltage and current into measured electrical power
#
# ``add_power`` is deliberately simple: P = V × I. Eclipse, spacecraft
# attitude and free rotation remain visible in the raw measured signal.

powered = opv.add_power(telemetry)
powered = powered[np.isfinite(powered["power_w"])].copy()

fig, ax = plt.subplots(figsize=(10, 4.8))
for panel_id, panel in powered.groupby("panel_id", sort=True):
    stride = max(1, len(panel) // 2500)
    shown = panel.iloc[::stride]
    ax.plot(shown["timestamp"], shown["power_w"], ".", ms=2, alpha=0.55, label=panel_id)
ax.set(xlabel="UTC time", ylabel="Measured panel power [W]")
ax.set_title("Step 4 — Measured solar-panel electrical power")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=7, ncols=2)
fig.autofmt_xdate()
plt.show()

# %% Step 5 — Compare each panel's upper power envelope
#
# A tumbling CubeSat naturally produces many low-power samples. Instead of
# interpreting every low point as a fault, we compare the daily 95th-percentile
# envelope for each panel.

powered["day"] = powered["timestamp"].dt.floor("D")
daily_p95 = powered.groupby(["panel_id", "day"], as_index=False).agg(
    power_p95_w=("power_w", lambda values: float(values.quantile(0.95))),
    samples=("power_w", "size"),
)

fig, ax = plt.subplots(figsize=(10, 4.8))
for panel_id, panel in daily_p95.groupby("panel_id", sort=True):
    ax.plot(panel["day"], panel["power_p95_w"], marker=".", ms=4, label=panel_id)
ax.set(xlabel="UTC day", ylabel="Daily 95th-percentile power [W]")
ax.set_title("Step 5 — Daily upper-envelope power by panel")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=7, ncols=2)
fig.autofmt_xdate()
plt.show()

# %% Step 6 — Normalize each panel and screen for persistent health changes
#
# OrbitalPV's telemetry-only baseline normalizes each panel to its own early
# high-power reference. This is an exploratory health indicator rather than a
# physics-normalized performance ratio.

normalized = opv.add_robust_baseline(powered.drop(columns=["day"]))
health = opv.daily_health(normalized, anomaly_threshold=4.0)

fig, ax = plt.subplots(figsize=(10, 4.8))
for panel_id, panel in health.groupby("panel_id", sort=True):
    ax.plot(panel["day"], panel["power_envelope"], marker=".", ms=4, label=panel_id)
    flagged = panel[panel["is_anomaly"]]
    ax.scatter(flagged["day"], flagged["power_envelope"], marker="x", s=28)
ax.axhline(1.0, linestyle="--", linewidth=1, label="Early reference")
ax.set(xlabel="UTC day", ylabel="Normalized upper-envelope power")
ax.set_title("Step 6 — Exploratory panel health and flagged low-envelope days")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=7, ncols=2)
fig.autofmt_xdate()
plt.show()

# %% Step 7 — Summarize panel-to-panel behavior
#
# We compare early and late median upper-envelope power. This does not assign
# the BIRDS expert fault label; it simply shows which panel histories deserve
# closer engineering investigation.

summary_rows = []
for panel_id, panel in health.groupby("panel_id", sort=True):
    panel = panel.sort_values("day")
    window = max(3, min(10, len(panel) // 4))
    early = float(panel.head(window)["power_envelope"].median())
    late = float(panel.tail(window)["power_envelope"].median())
    summary_rows.append(
        {
            "panel_id": panel_id,
            "early_envelope": early,
            "late_envelope": late,
            "relative_change_percent": 100.0 * (late / early - 1.0) if early else np.nan,
            "flagged_days": int(panel["is_anomaly"].sum()),
        }
    )

panel_summary = pd.DataFrame(summary_rows).sort_values("relative_change_percent")
print(panel_summary.to_string(index=False))

fig, ax = plt.subplots(figsize=(8.5, 4.5))
ax.bar(panel_summary["panel_id"], panel_summary["relative_change_percent"])
ax.axhline(0.0, linewidth=1)
ax.set(xlabel="Panel", ylabel="Late vs early envelope change [%]")
ax.set_title("Step 7 — Panel-level change for engineering follow-up")
ax.grid(True, axis="y", alpha=0.3)
plt.show()
