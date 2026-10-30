"""
Schedule computing around sunlight and battery limits
=====================================================

Compare identical requested compute energy with continuous versus deferrable
execution. This synthetic scenario uses a deadline heuristic and a steady
radiator bound. It is not an optimized design or a real data-center forecast.
"""

import matplotlib.pyplot as plt
import numpy as np

from orbitalpv import physics as opv

period = 5400
time = np.arange(0, 6 * period + 60, 60)
generation = np.where(time[:-1] % period < 3240, 45.0, 0.0)
battery = opv.BatterySpec(25, initial_soc=0.8, minimum_soc=0.2, max_charge_w=30, max_discharge_w=30)
radiator = opv.radiator_feasibility(
    38,
    area_m2=0.08,
    radiator_temperature_k=320,
    emissivity=0.9,
    absorbed_environment_w_m2=50,
)
thermal_limit = float(radiator["available_heat_rejection_w"])
continuous = opv.dispatch_power(
    time, generation, 16, battery=battery, maximum_served_power_w=thermal_limit
)
tasks = [opv.ComputeTask(12, i * period, (i + 1) * period, 30) for i in range(6)]
scheduled, completion = opv.schedule_compute_workload(
    time,
    generation,
    8,
    battery=battery,
    tasks=tasks,
    compute_power_limit_w=30,
    thermal_power_limit_w=thermal_limit,
)

fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
hours = time[1:] / 3600
axes[0].step(hours, generation, label="Solar generation", alpha=0.6)
axes[0].step(hours, scheduled.served_load_w, label="Base + scheduled computing")
axes[0].axhline(thermal_limit, color="red", linestyle=":", label="Steady radiator bound")
axes[0].set(ylabel="Power [W]", title="Same compute energy, different timing")
axes[0].legend(fontsize=8, ncol=3)
axes[1].plot(hours, continuous.soc_end, label="Continuous computing")
axes[1].plot(hours, scheduled.soc_end, label="Sunlight-preferred computing")
axes[1].set(xlabel="Elapsed time [h]", ylabel="Battery state of charge")
axes[1].legend(fontsize=8)
for axis in axes:
    axis.grid(alpha=0.25)
fig.tight_layout()
print(f"Completed compute energy: {completion.completed_energy_wh.sum():.1f} Wh")
print(f"Missed deadline energy: {completion.unserved_energy_wh.sum():.1f} Wh")
plt.show()
