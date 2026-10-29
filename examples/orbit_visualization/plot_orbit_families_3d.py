"""
Representative Earth orbit families
===================================

Plot common circular-orbit families around Earth using the public OrbitalPV API.
"""

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv

EARTH_RADIUS_KM = opv.EARTH_EQUATORIAL_RADIUS_M / 1000.0

orbits = {
    "LEO · 550 km · 51.6°": opv.circular_orbit_positions_m(550_000.0, 51.6, samples=721) / 1000.0,
    "Polar/SSO-like · 700 km · 97.4°": opv.circular_orbit_positions_m(
        700_000.0, 97.4, raan_deg=70.0, samples=721
    )
    / 1000.0,
    "MEO · 20,200 km · 55°": opv.circular_orbit_positions_m(
        20_200_000.0, 55.0, raan_deg=135.0, samples=721
    )
    / 1000.0,
    "GEO · 35,786 km · 0°": opv.circular_orbit_positions_m(35_786_000.0, 0.0, samples=721) / 1000.0,
}

fig = plt.figure(figsize=(9, 8))
ax = fig.add_subplot(111, projection="3d")

u = np.linspace(0.0, 2.0 * np.pi, 80)
v = np.linspace(0.0, np.pi, 40)
x = EARTH_RADIUS_KM * np.outer(np.cos(u), np.sin(v))
y = EARTH_RADIUS_KM * np.outer(np.sin(u), np.sin(v))
z = EARTH_RADIUS_KM * np.outer(np.ones_like(u), np.cos(v))
ax.plot_surface(x, y, z, alpha=0.22, linewidth=0)

for label, xyz in orbits.items():
    ax.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], label=label)

limit = EARTH_RADIUS_KM + 39_000.0
ax.set_xlim(-limit, limit)
ax.set_ylim(-limit, limit)
ax.set_zlim(-limit, limit)
ax.set_box_aspect((1, 1, 1))
ax.set(xlabel="ECI x [km]", ylabel="ECI y [km]", zlabel="ECI z [km]")
ax.set_title("Representative orbit families around Earth")
ax.legend(loc="upper left", fontsize=8)
plt.show()
