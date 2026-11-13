"""
Solar-powered AI clusters: links, formation, radiation and cost
=======================================================================

Explore arXiv:2511.19468v2 (Agüera y Arcas et al., Google, June 2026) with
version-pinned, manually curated evidence. The paper reports a short-path
800 Gbps one-way optical demonstration, not an operational orbital AI cluster.
The optical curves and HCW formation below are engineering approximations;
the power, thermal and cost comparison uses explicit synthetic assumptions.

Run ``python analysis/space_ai_cluster/run.py`` to export nine CSV tables and
input provenance. This example uses packaged data and makes no network calls.
See the :doc:`modeling guide </user_guide/modeling_topics/space_ai_cluster>`
for equations, evidence boundaries, direction conventions and exclusions.
"""

import matplotlib.pyplot as plt
import numpy as np

from orbitalpv.orbit import circular_orbit_period_s
from orbitalpv.space_ai import FormationSpec, hcw_formation, load_space_ai_evidence
from orbitalpv.space_ai_analysis import space_ai_trade_study

# %% Pin the paper version and preserve the status of each group of inputs.
evidence = load_space_ai_evidence()
tables = space_ai_trade_study(evidence)
colors = ["#157F91", "#CA8730", "#785AA0", "#C5524B"]
plt.rcParams.update({"axes.titlesize": 11, "axes.labelsize": 9, "font.size": 9})
fig, axes = plt.subplots(2, 3, figsize=(15, 9), layout="constrained")
fig.suptitle(
    "Solar-powered AI in orbit | Evidence and engineering screens", fontsize=17, weight="bold"
)

# %% Far-field optical ceiling; near-field geometry needs a different model.
links = tables["optical_links"]
ax = axes[0, 0]
ax.loglog(
    links.distance_km, links.photon_ceiling_gbps / 1000, color=colors[0], label="Photon ceiling"
)
ax.loglog(
    links.distance_km,
    links.screened_rate_gbps / 1000,
    color=colors[1],
    label="With electronics cap",
)
ax.axhline(9.6, color="#555555", linestyle=":", label="24 x 400 Gbps convention")
ax.set(
    xlabel="Separation [km]",
    ylabel="One-direction ceiling [Tbps]",
    title="5 W, 10 cm optics | far field only",
)
ax.legend(fontsize=8)

# %% An independent bounded HCW lattice uses the paper's 81-satellite scale.
spec = FormationSpec(**evidence["formation"]["inputs"])
period = circular_orbit_period_s(spec.altitude_m)
ax = axes[0, 1]
for fraction, color in zip((0, 0.125), colors[:2], strict=True):
    state = hcw_formation([period * fraction], spec)[0]
    ax.scatter(state[:, 1], state[:, 0], s=12, color=color, label=f"t = {fraction:g} orbit")
ax.set(xlabel="Along-track y [m]", ylabel="Radial x [m]", title="81 satellites | ideal HCW, no J2")
ax.set_aspect("equal")
ax.legend(fontsize=8)

# %% Existing solar/battery/radiator models bound continuous compute electrical power.
compute = tables["compute_screen"]
ax = axes[0, 2]
bars = ax.barh(compute.scenario, compute.sustainable_compute_kw, color=colors)
ax.bar_label(bars, fmt="%.1f", padding=3)
ax.axvline(20, color="#555555", linestyle=":")
ax.invert_yaxis()
ax.set(
    xlabel="Continuous compute electrical power [kW]",
    xlim=(0, 23),
    title="Analyst scenarios | 20 kW target",
)

# %% Conditional event rates are not a measured system reliability prediction.
events = tables["radiation_events"].set_index("event_kind")
names = ["tpu_sdc_nominal", "hbm_uecc", "tpu_sefi", "host_cpu_sefi", "host_ram_sefi"]
ax = axes[1, 0]
ax.barh(
    ["TPU SDC", "HBM UECC", "TPU SEFI", "Host CPU SEFI", "Host RAM SEFI"],
    events.loc[names, "events_per_device_year"],
    color=colors[2],
)
ax.set_xscale("log")
ax.invert_yaxis()
ax.set(
    xlabel="Expected events per device-year [log scale]", title="Conditional on 150 rad(Si)/year"
)

# %% A launch learning curve is conditional on cumulative mass, not a launch date.
ax = axes[1, 1]
for (learning, group), color in zip(
    tables["learning_curve"].groupby("learning_rate"), colors, strict=False
):
    ax.loglog(
        group.cumulative_mass_t,
        group.price_usd_kg,
        label=f"{learning:.0%} learning rate",
        color=color,
    )
ax.axhline(200, color="#555555", linestyle=":", label="Scenario: $200/kg")
ax.set(
    xlabel="Cumulative launched mass [t]",
    ylabel="Conditional launch price [USD/kg]",
    title="Learning sensitivity | no date forecast",
)
ax.legend(fontsize=8)

# %% Recompute Table 1 without hiding the differences from rounded paper values.
costs = tables["launched_power"].query("launch_price_usd_kg == 200")
ax = axes[1, 2]
x = np.arange(len(costs))
ax.bar(x - 0.18, costs.calculated_usd_kw_year, width=0.36, label="Calculated", color=colors[0])
ax.bar(
    x + 0.18, costs.paper_reported_usd_kw_year, width=0.36, label="Paper reported", color=colors[1]
)
ax.set_xticks(x, ["Starlink v2", "Starlink v1", "OneWeb", "Iridium"], rotation=15)
ax.set(ylabel="Launch-only USD / nameplate kW-year", title="Table 1 proxies | $200/kg scenario")
ax.legend(fontsize=8)
for ax in axes.flat:
    ax.grid(alpha=0.15)
    ax.spines[["top", "right"]].set_visible(False)
plt.show()

# %% Read the explicit geometric and business-screen outputs.
print("Near-field geometry only; no qualified multiplexed throughput:")
print(tables["spatial_geometry"].to_string(index=False))
print("Launch-only/electricity cost parity, excluding all other costs:")
print(compute[["scenario", "launch_only_energy_cost_parity_usd_kg"]].to_string(index=False))

# The paper's 9.6 Tbps direction label is ambiguous; the model explicitly assumes
# 400 Gbps per channel per direction and never doubles the reported benchmark.
# The bench demonstration, analytical capacity and synthetic useful power are
# separate evidence classes. Compute kW is not FLOPS, tokens/s or training speed.
