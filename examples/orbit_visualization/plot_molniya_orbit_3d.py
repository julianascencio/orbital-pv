"""
Molniya-style highly elliptical orbit
=====================================

Visualize a representative highly elliptical orbit with the characteristic
63.4° critical inclination used by Molniya-style missions.

The orbit is an illustrative geometry, not a propagated operational satellite.
"""

import matplotlib.pyplot as plt
import numpy as np

EARTH_RADIUS_KM = 6378.137


def perifocal_to_eci(
    xyz_perifocal: np.ndarray,
    inclination_deg: float,
    raan_deg: float,
    argument_of_perigee_deg: float,
) -> np.ndarray:
    """Rotate perifocal coordinates into an Earth-centered inertial frame."""
    inclination = np.deg2rad(inclination_deg)
    raan = np.deg2rad(raan_deg)
    argument = np.deg2rad(argument_of_perigee_deg)

    c_raan, s_raan = np.cos(raan), np.sin(raan)
    c_inc, s_inc = np.cos(inclination), np.sin(inclination)
    c_arg, s_arg = np.cos(argument), np.sin(argument)

    rotation = np.array(
        [
            [
                c_raan * c_arg - s_raan * s_arg * c_inc,
                -c_raan * s_arg - s_raan * c_arg * c_inc,
                s_raan * s_inc,
            ],
            [
                s_raan * c_arg + c_raan * s_arg * c_inc,
                -s_raan * s_arg + c_raan * c_arg * c_inc,
                -c_raan * s_inc,
            ],
            [s_arg * s_inc, c_arg * s_inc, c_inc],
        ]
    )
    return xyz_perifocal @ rotation.T


perigee_altitude_km = 600.0
apogee_altitude_km = 39_700.0
r_perigee = EARTH_RADIUS_KM + perigee_altitude_km
r_apogee = EARTH_RADIUS_KM + apogee_altitude_km
semi_major_axis = 0.5 * (r_perigee + r_apogee)
eccentricity = (r_apogee - r_perigee) / (r_apogee + r_perigee)
semi_latus_rectum = semi_major_axis * (1.0 - eccentricity**2)

true_anomaly = np.linspace(0.0, 2.0 * np.pi, 1000)
radius = semi_latus_rectum / (1.0 + eccentricity * np.cos(true_anomaly))
perifocal = np.column_stack(
    (radius * np.cos(true_anomaly), radius * np.sin(true_anomaly), np.zeros_like(radius))
)
orbit = perifocal_to_eci(
    perifocal,
    inclination_deg=63.4,
    raan_deg=35.0,
    argument_of_perigee_deg=270.0,
)

fig = plt.figure(figsize=(9, 8))
ax = fig.add_subplot(111, projection="3d")

u = np.linspace(0.0, 2.0 * np.pi, 80)
v = np.linspace(0.0, np.pi, 40)
x = EARTH_RADIUS_KM * np.outer(np.cos(u), np.sin(v))
y = EARTH_RADIUS_KM * np.outer(np.sin(u), np.sin(v))
z = EARTH_RADIUS_KM * np.outer(np.ones_like(u), np.cos(v))
ax.plot_surface(x, y, z, alpha=0.22, linewidth=0)
ax.plot(orbit[:, 0], orbit[:, 1], orbit[:, 2], label="Molniya-style orbit")

apogee_index = int(np.argmax(np.linalg.norm(orbit, axis=1)))
perigee_index = int(np.argmin(np.linalg.norm(orbit, axis=1)))
ax.scatter(*orbit[apogee_index], marker="o", label="Apogee")
ax.scatter(*orbit[perigee_index], marker="x", label="Perigee")

limit = r_apogee * 1.08
ax.set_xlim(-limit, limit)
ax.set_ylim(-limit, limit)
ax.set_zlim(-limit, limit)
ax.set_box_aspect((1, 1, 1))
ax.set(xlabel="ECI x [km]", ylabel="ECI y [km]", zlabel="ECI z [km]")
ax.set_title("Representative Molniya-style orbit around Earth")
ax.legend(loc="upper left")
plt.show()
