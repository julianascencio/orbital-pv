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

counts = telemetry["panel_id"].value_counts()
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
# ``add_power`` is deliberately simple: P = V x I. Eclipse, spacecraft
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

# %% Step 5 — Compare each measurement session's upper power envelope
#
# The RAAVANA workbook contains dated high-sampling campaigns. A tumbling
# CubeSat naturally produces many low-power samples, so we compare each
# session's 95th-percentile power instead of treating every low point as a
# fault.

session_p95 = powered.groupby(["panel_id", "source_sheet"], as_index=False).agg(
    power_p95_w=("power_w", lambda values: float(values.quantile(0.95))),
    samples=("power_w", "size"),
)

session_order = list(dict.fromkeys(powered["source_sheet"].astype(str)))
session_rank = {name: index for index, name in enumerate(session_order)}
session_p95["session_rank"] = session_p95["source_sheet"].astype(str).map(session_rank)
session_p95 = session_p95.sort_values(["panel_id", "session_rank"])

fig, ax = plt.subplots(figsize=(9, 4.8))
for _panel_id, panel in session_p95.groupby("panel_id", sort=True):
    ax.plot(
        panel["session_rank"],
        panel["power_p95_w"],
        marker="o",
        label=panel_id,
    )
ax.set(
    xlabel="Measurement campaign",
    ylabel="Session 95th-percentile power [W]",
    xticks=range(len(session_order)),
    xticklabels=session_order,
)
ax.set_title("Step 5 — Upper-envelope power by real measurement campaign")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=7, ncols=2)
plt.xticks(rotation=20)
plt.show()

# %% Step 6 — Normalize each panel to its first measurement campaign
#
# This creates a simple relative health indicator. It is deliberately not a
# flight-qualified fault classifier: spacecraft attitude, beta angle,
# temperature and operating state are not yet normalized.

pieces = []
for _panel_id, panel in session_p95.groupby("panel_id", sort=True):
    panel = panel.copy().sort_values("session_rank")
    reference = float(panel.iloc[0]["power_p95_w"])
    panel["relative_envelope"] = panel["power_p95_w"] / reference if reference else np.nan
    panel["screen_low"] = panel["relative_envelope"] < 0.80
    pieces.append(panel)
session_health = pd.concat(pieces, ignore_index=True)

fig, ax = plt.subplots(figsize=(9, 4.8))
for panel_id, panel in session_health.groupby("panel_id", sort=True):
    ax.plot(
        panel["session_rank"],
        panel["relative_envelope"],
        marker="o",
        label=panel_id,
    )
    flagged = panel[panel["screen_low"]]
    ax.scatter(flagged["session_rank"], flagged["relative_envelope"], marker="x", s=45)
ax.axhline(1.0, linestyle="--", linewidth=1, label="First-session reference")
ax.axhline(0.8, linestyle=":", linewidth=1, label="Exploratory 80% screen")
ax.set(
    xlabel="Measurement campaign",
    ylabel="Relative upper-envelope power",
    xticks=range(len(session_order)),
    xticklabels=session_order,
)
ax.set_title("Step 6 — Relative panel health screen")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=7, ncols=2)
plt.xticks(rotation=20)
plt.show()

# %% Step 7 — Summarize first-to-last campaign changes
#
# The source publication reports a RAAVANA panel failure. We do not assign that
# expert label here; we rank the measured panel changes so an engineer can see
# which panel history deserves closer investigation.

summary_rows = []
for panel_id, panel in session_health.groupby("panel_id", sort=True):
    panel = panel.sort_values("session_rank")
    first = float(panel.iloc[0]["power_p95_w"])
    last = float(panel.iloc[-1]["power_p95_w"])
    summary_rows.append(
        {
            "panel_id": panel_id,
            "first_p95_w": first,
            "last_p95_w": last,
            "relative_change_percent": 100.0 * (last / first - 1.0) if first else np.nan,
            "screened_campaigns": int(panel["screen_low"].sum()),
        }
    )

panel_summary = pd.DataFrame(summary_rows).sort_values("relative_change_percent")
print(panel_summary.to_string(index=False))

fig, ax = plt.subplots(figsize=(8.5, 4.5))
ax.bar(panel_summary["panel_id"], panel_summary["relative_change_percent"])
ax.axhline(0.0, linewidth=1)
ax.set(xlabel="Panel", ylabel="Last vs first campaign change [%]")
ax.set_title("Step 7 — Real panel changes for engineering follow-up")
ax.grid(True, axis="y", alpha=0.3)
plt.show()

# %% Step 8 — Screen for persistent cross-panel imbalance
#
# A panel can already be impaired in the first available campaign, in which
# case a first-vs-last comparison will not reveal the condition. We therefore
# also compare each panel's typical campaign upper envelope with the median
# across all five faces. Because spacecraft attitude is not normalized, this is
# an engineering screening metric rather than a definitive fault label.
#
# The BIRDS publication reports a solar-panel failure on RAAVANA. A panel that
# remains orders of magnitude below its peers is qualitatively consistent with
# that report, but this example does not infer the authors' expert label.

panel_level = (
    session_p95.groupby("panel_id", as_index=False)
    .agg(typical_p95_w=("power_p95_w", "median"))
    .sort_values("typical_p95_w")
)
fleet_median = float(panel_level["typical_p95_w"].median())
panel_level["relative_to_panel_median"] = (
    panel_level["typical_p95_w"] / fleet_median if fleet_median else np.nan
)

print("\nCross-panel upper-envelope comparison")
print(panel_level.to_string(index=False))

fig, ax = plt.subplots(figsize=(8.5, 4.5))
ax.bar(panel_level["panel_id"], panel_level["relative_to_panel_median"])
ax.axhline(1.0, linestyle="--", linewidth=1, label="Median panel")
ax.axhline(0.2, linestyle=":", linewidth=1, label="Exploratory 20% screen")
ax.set(xlabel="Panel", ylabel="Typical envelope / median panel envelope")
ax.set_title("Step 8 — Persistent cross-panel imbalance screen")
ax.grid(True, axis="y", alpha=0.3)
ax.legend()
plt.show()
