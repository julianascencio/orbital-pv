"""
PV and battery sizing for a continuous lunar load
===================================================

Enumerate a 1 kW payload plus a 103 W equivalent-conductance heater scenario.
Require no unmet load and a final state of charge at least equal to the initial
50%. Mass includes only illustrative panels (3 kg/m²) and batteries (150 Wh/kg).
Terrain, batteries, thermal equipment and operating dates need mission-specific
validation; these discrete candidate sizes are not an optimal flight design.
"""

import matplotlib.pyplot as plt
import numpy as np
from _lunar_analysis import analysis

from orbitalpv import physics

cases = analysis.storage_cases("01", 5)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
for feasible, marker, label in [
    (False, "x", "Fails load or final SOC"),
    (True, "o", "Meets model constraints"),
]:
    subset = cases[cases.feasible == feasible]
    axes[0].scatter(
        subset.array_area_m2,
        subset.capacity_wh / 1000,
        c=subset.scenario_mass_kg,
        cmap="viridis",
        vmin=cases.scenario_mass_kg.min(),
        vmax=cases.scenario_mass_kg.max(),
        marker=marker,
        s=65,
        label=label,
    )
axes[0].set(
    xlabel="Array area [m²]",
    ylabel="Nominal battery capacity [kWh]",
    yscale="log",
    title="5 m tower at illustrative Site01 point",
)
axes[0].legend(fontsize=8)
feasible = cases[cases.feasible]
if feasible.empty:
    axes[1].text(
        0.5, 0.5, "No feasible candidate in this grid", ha="center", transform=axes[1].transAxes
    )
else:
    best = feasible.iloc[0]
    p = analysis.profile("01", 5)
    dispatch = physics.dispatch_power(
        p.time_s,
        p.dc_power_w.to_numpy()[:-1] * best.array_area_m2,
        1103,
        battery=physics.BatterySpec(
            float(best.capacity_wh),
            initial_soc=0.5,
            minimum_soc=0.1,
            maximum_soc=0.95,
            max_charge_w=15000,
            max_discharge_w=3000,
        ),
    )
    axes[1].plot(p.time_s.to_numpy()[1:] / 86400, dispatch.soc_end, color="#398c99", lw=1)
    axes[1].axhline(0.1, ls="--", color="#c77629", label="Minimum SOC")
    axes[1].set(
        xlabel="Elapsed Earth days in 2026",
        ylabel="Battery state of charge",
        title=f"Lowest scenario mass: {best.array_area_m2:g} m² + {best.capacity_wh / 1000:g} kWh",
        ylim=(0, 1),
    )
    print(best.to_string())
    print("Unserved energy [Wh]:", float(np.sum(dispatch.unserved_load_w * dispatch.duration_h)))
for ax in axes:
    ax.grid(alpha=0.2)
plt.show()
