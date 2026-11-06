"""
How much customer power can a lunar utility commit?
===================================================

Astrolab's November 4, 2026 LUMIS announcement motivates screening continuous
power-service commitments. Its ratings and endurance are design claims, not
flight-verified customer delivery. Source:
https://www.astrolab.space/2026/11/04/astrolab-unveils-lumis-power-and-communications-node-for-lunar-operations/

All battery sizes, housekeeping, delivery losses and illumination intervals
below are assumptions. The 400-hour dark interval is a synthetic stress case,
not a measured lunar site or a verified interpretation of the reserve claim.
"""

from pathlib import Path

import matplotlib.pyplot as plt

from orbitalpv.data import load_table
from orbitalpv.physics import BatterySpec
from orbitalpv.utility import screen_power_service

directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
cases = load_table(directory / "_data/lunar_utility_cases.csv")
fig, axes = plt.subplots(1, 2, figsize=(11, 5), layout="constrained")
labels, limits = [], []
for row in cases.to_dict("records"):
    battery = BatterySpec(
        float(row["battery_wh"]),
        initial_soc=0.9,
        minimum_soc=0.2,
        maximum_soc=0.95,
        max_charge_w=20000,
        max_discharge_w=20000,
    )
    result = screen_power_service(
        [0, row["dark_h"] * 3600, (row["dark_h"] + row["sun_h"]) * 3600],
        [0, row["pv_w"]],
        50,
        list(range(13)),
        customer_power_w=50,
        delivery_efficiency=0.9,
        battery=battery,
    )
    feasible = result[result.repeatable_profile_feasible]
    limit = int(feasible.customers.max()) if len(feasible) else 0
    labels.append(row["scenario"])
    limits.append(limit)
    axes[1].plot(result.customers, result.unserved_bus_wh / 1000, marker=".", label=row["scenario"])
    print(f"{row['scenario']}: {limit} continuous 50 W customers within candidate grid")
axes[0].bar(labels, limits, color=["#167d9a", "#e7ae4c", "#5a9461", "#9467bd"])
axes[0].set(ylabel="Admissible continuous 50 W customers", title="Modeled service commitments")
axes[0].tick_params(axis="x", labelrotation=28)
axes[1].set(
    xlabel="Requested customers",
    ylabel="Unserved utility-bus energy [kWh]",
    title="Overcommitment exposes shortfall",
)
axes[1].legend(fontsize=8)
axes[1].grid(alpha=0.2)
plt.show()

# %% A service promise needs a load, reserve policy and recharge test
# Increasing the PV rating alone cannot cover additional dark-interval energy.
# The method also rejects initially charged storage that fails to recharge.
# Demand is screened in aggregate: unmet energy is not assigned to customers
# or housekeeping. These are conditional capacity limits, not tariff advice,
# actual LUMIS specifications, guaranteed service levels or reliability estimates.
