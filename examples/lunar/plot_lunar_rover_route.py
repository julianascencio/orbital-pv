"""
Rover routing with terrain, sunlight and battery reserve
==========================================================

Find the earliest feasible arrival on a small measured-terrain grid. Costs
include rolling resistance, ascent, housekeeping, heating and battery losses.
Solar power uses computed terrain shadows and an illustrative tracking array.
The four-neighbour planner can wait to charge. Slopes below grid resolution,
wheel slip, obstacles smaller than a cell and actual rover calibration are absent.
The 12-hour July window is selected for the largest spatial solar-power spread,
so it illustrates mixed lighting rather than average mission conditions.
"""

import matplotlib.pyplot as plt
import numpy as np
from _lunar_analysis import analysis

from orbitalpv import lunar

terrain, time, solar, rover = analysis.rover_inputs()
path = lunar.energy_aware_route(
    terrain.elevation_m,
    time,
    solar,
    cell_size_m=50,
    start=(6, 0),
    goal=(6, 6),
    rover=rover,
    heater_power_w=10,
)
x, y, _ = analysis.point("01")
fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
for ax, values, title, units in [
    (axes[0], terrain.elevation_m, "Measured/interpolated terrain", "Elevation [m]"),
    (axes[1], np.mean(solar, axis=0), "Modelled mean available rover PV", "Power [W]"),
]:
    im = ax.pcolormesh(terrain.x_m - x, terrain.y_m - y, values, shading="auto", cmap="viridis")
    ax.plot(
        terrain.x_m[path.column.to_numpy(int)] - x,
        terrain.y_m[path.row.to_numpy(int)] - y,
        "w.-",
        lw=2,
    )
    fig.colorbar(im, ax=ax, label=units)
    ax.set(
        xlabel="Projected X offset [m]",
        ylabel="Projected Y offset [m]",
        title=title,
        aspect="equal",
    )
axes[2].plot(path.time_s / 3600, path.energy_wh, "o-", color="#398c99")
axes[2].axhline(rover.reserve_wh, color="#c77629", ls="--", label="Required reserve")
axes[2].set(
    xlabel="Elapsed time [h]",
    ylabel="Stored battery energy [Wh]",
    title="Energy along feasible route",
)
axes[2].legend(fontsize=8)
axes[2].grid(alpha=0.2)
print(path.to_string(index=False))
plt.show()
