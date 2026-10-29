"""
Molniya-style highly elliptical orbit
=====================================

Generate a representative Molniya-style ellipse with the public OrbitalPV API.
"""

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv

EARTH_RADIUS_KM = opv.EARTH_EQUATORIAL_RADIUS_M / 1000.0
perigee_altitude_km = 600.0
apogee_altitude_km = 39_700.0
r_perigee_km = EARTH_RADIUS_KM + perigee_altitude_km
r_apogee_km = EARTH_RADIUS_KM + apogee_altitude_km
semi_major_axis_m = 0.5 * (r_perigee_km + r_apogee_km) * 1000.0
eccentricity = (r_apogee_km - r_perigee_km) / (r_apogee_km + r_perigee_km)

orbit_km = (
    opv.keplerian_orbit_positions_m(
        semi_major_axis_m,
        eccentricity,
        inclination_deg=63.4,
        raan_deg=35.0,
        argument_of_periapsis_deg=270.0,
        samples=1000,
    )
    / 1000.0
)

fig = plt.figure(figsize=(9, 8))
ax = fig.add_subplot(111, projection="3d")

u = np.linspace(0.0, 2.0 * np.pi, 80)
v = np.linspace(0.0, np.pi, 40)
x = EARTH_RADIUS_KM * np.outer(np.cos(u), np.sin(v))
y = EARTH_RADIUS_KM * np.outer(np.sin(u), np.sin(v))
z = EARTH_RADIUS_KM * np.outer(np.ones_like(u), np.cos(v))
ax.plot_surface(x, y, z, alpha=0.22, linewidth=0)
ax.plot(orbit_km[:, 0], orbit_km[:, 1], orbit_km[:, 2], label="Molniya-style orbit")

radius_km = np.linalg.norm(orbit_km, axis=1)
apogee_index = int(np.argmax(radius_km))
perigee_index = int(np.argmin(radius_km))
ax.scatter(*orbit_km[apogee_index], marker="o", label="Apogee")
ax.scatter(*orbit_km[perigee_index], marker="x", label="Perigee")

limit = r_apogee_km * 1.08
ax.set_xlim(-limit, limit)
ax.set_ylim(-limit, limit)
ax.set_zlim(-limit, limit)
ax.set_box_aspect((1, 1, 1))
ax.set(xlabel="ECI x [km]", ylabel="ECI y [km]", zlabel="ECI z [km]")
ax.set_title("Representative Molniya-style orbit around Earth")
ax.legend(loc="upper left")
plt.show()
