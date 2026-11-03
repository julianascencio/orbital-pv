"""
Tower height, tracking and longest darkness
=============================================

Compare three illustrative points in NASA PGDA Sites 01, 04 and 11, with 2, 5
and 20 m panel elevations. Fixed arrays are vertical and face true north;
tracking is ideal two-axis with no motor consumption or mutual shading.
Darkness means <=1% of the solar disc visible, resolved at two-hour steps.
"""

import matplotlib.pyplot as plt
from _lunar_analysis import analysis

from orbitalpv import lunar

summary = analysis.compare_sites()
# The public darkness metric uses interval boundaries and explicit visibility.
p = analysis.profile("01", 5)
print(
    "Site01 longest darkness [h]:",
    lunar.longest_darkness_hours(
        p.time_s,
        (p.terrain_visible_fraction * p.earth_visible_fraction).to_numpy()[:-1],
    ),
)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
for site, color in [("01", "#c77629"), ("04", "#398c99"), ("11", "#7565a8")]:
    for mode, style in [("sun_tracking", "-"), ("fixed", "--")]:
        values = summary[(summary.site == site) & (summary["mode"] == mode)]
        axes[0].plot(
            values.tower_height_m,
            values.energy_kwh_m2,
            style,
            marker="o",
            color=color,
            label=f"Site {site} · {mode.replace('_', ' ')}",
        )
    values = summary[(summary.site == site) & (summary["mode"] == "sun_tracking")]
    axes[1].plot(
        values.tower_height_m, values.longest_darkness_h, "o-", color=color, label=f"Site {site}"
    )
axes[0].set(
    ylabel="Modelled 2026 DC yield [kWh/m²]", title="Height benefit depends on local terrain"
)
axes[1].set(
    ylabel="Longest modelled darkness [hours]",
    title="More annual energy does not guarantee survival",
)
for ax in axes:
    ax.set_xlabel("Panel height above ground [m]")
    ax.set_xticks([2, 5, 20])
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
print(summary.to_string(index=False))

# %%
# Compare the best feasible PV/battery candidate at each height, adding an
# explicitly assumed tower mass of 20 kg + 5 kg/m. This is a design-grid sweep,
# not a structural analysis or a globally optimal lunar installation.
tradeoff = analysis.tower_tradeoff("01")
fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
valid = tradeoff[tradeoff.feasible]
ax.bar(
    valid.tower_height_m.astype(str),
    valid.scenario_mass_kg,
    label="PV + battery scenario",
    color="#398c99",
)
ax.bar(
    valid.tower_height_m.astype(str),
    valid.tower_mass_kg,
    bottom=valid.scenario_mass_kg,
    label="Assumed tower",
    color="#c77629",
)
ax.set(
    xlabel="Tower height [m]",
    ylabel="Modelled component mass [kg]",
    title="Site01: lowest feasible mass among tested candidates",
)
ax.legend(fontsize=8)
print(tradeoff.to_string(index=False))

# %%
# Numerical sensitivity is material: a coarse azimuth envelope can connect
# separate shadow events. This comparison is not a confidence interval.
sensitivity = analysis.resolution_sensitivity()
fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), layout="constrained")
for step, values in sensitivity.groupby("timestep_h"):
    degrees = 360 / values.azimuth_bins
    axes[0].plot(degrees, values.july_30day_energy_kwh_m2, "o-", label=f"{step:g} h time step")
    axes[1].plot(degrees, values.longest_darkness_h, "o-", label=f"{step:g} h time step")
axes[0].set(ylabel="July 30-day yield [kWh/m²]", title="Refining the horizon changes yield")
axes[1].set(ylabel="Longest darkness [h]", title="Outage duration needs resolution checks")
for ax in axes:
    ax.set(xlabel="Horizon sector width [degrees]", xticks=[1, 2, 4])
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
print(sensitivity.to_string(index=False))
plt.show()
