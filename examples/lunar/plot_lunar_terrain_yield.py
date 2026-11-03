"""
Measured lunar terrain to a local PV yield map
================================================

Recompute a small annual-yield grid around an illustrative high point in PGDA
Site01. Three nested LOLA grids resolve nearby terrain and distant horizons.
The 5 m grid contains interpolation; the 9x9 yield map is a coarse screening
experiment, not a landing-site recommendation. Cells are held at 25 C.
"""

import matplotlib.pyplot as plt
import numpy as np
from _lunar_analysis import analysis

from orbitalpv import lunar

site = "01"
analysis.inputs()  # Verify the offline source manifest before loading.
with np.load(analysis.DATA / f"site{site}_5m.npz", allow_pickle=False) as source:
    terrain = lunar.LunarTerrain(source["x_m"], source["y_m"], source["elevation_m"])
xs, ys, energy = analysis.yield_map(site)
x, y, _ = analysis.point(site)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
im = axes[0].pcolormesh(
    (terrain.x_m - x) / 1000,
    (terrain.y_m - y) / 1000,
    terrain.elevation_m,
    shading="auto",
    cmap="terrain",
)
axes[0].plot(0, 0, "k+", ms=12)
fig.colorbar(im, ax=axes[0], label="LOLA elevation above lunar sphere [m]")
im = axes[1].pcolormesh((xs - x) / 1000, (ys - y) / 1000, energy, shading="auto", cmap="magma")
fig.colorbar(im, ax=axes[1], label="Modelled 2026 DC yield [kWh/m²]")
axes[0].set_title("Measured/interpolated terrain · 5 m grid")
axes[1].set_title("5 m tower · ideal tracking · 2-hour steps")
for ax in axes:
    ax.set(xlabel="Projected X offset [km]", ylabel="Projected Y offset [km]", aspect="equal")
print(f"Local modelled yield range: {np.min(energy):.0f}-{np.max(energy):.0f} kWh/m²/year")
plt.show()
