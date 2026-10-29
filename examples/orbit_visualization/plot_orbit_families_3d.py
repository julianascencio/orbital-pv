"""
Representative Earth orbit families
===================================

Plot several common circular-orbit families around Earth in one 3D view.

The geometry is generated from simple classical orbital elements so the
example remains deterministic and does not require network access.
"""

import matplotlib.pyplot as plt
import numpy as np

EARTH_RADIUS_KM = 6378.137


def orbit_xyz_km(
    radius_km: float,
    inclination_deg: float,
    raan_deg: float,
    argument_deg: np.ndarray,
) -> np.ndarray:
    """Return circular-orbit positions in a simple Earth-centered inertial frame."""
    inclination = np.deg2rad(inclination_deg)
    raan = np.deg2rad(raan_deg)

    x_pf = radius_km * np.cos(argument_deg)
    y_pf = radius_km * np.sin(argument_deg)

    x = np.cos(raan) * x_pf - np.sin(raan) * np.cos(inclination) * y_pf
    y = np.sin(raan) * x_pf + np.cos(raan) * np.cos(inclination) * y_pf
    z = np.sin(inclination) * y_pf
    return np.column_stack((x, y, z))


argument = np.linspace(0.0, 2.0 * np.pi, 721)

orbits = {
    "LEO · 550 km · 51.6°": orbit_xyz_km(EARTH_RADIUS_KM + 550.0, 51.6, 0.0, argument),
    "Polar/SSO-like · 700 km · 97.4°": orbit_xyz_km(EARTH_RADIUS_KM + 700.0, 97.4, 70.0, argument),
    "MEO · 20,200 km · 55°": orbit_xyz_km(EARTH_RADIUS_KM + 20_200.0, 55.0, 135.0, argument),
    "GEO · 35,786 km · 0°": orbit_xyz_km(EARTH_RADIUS_KM + 35_786.0, 0.0, 0.0, argument),
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
