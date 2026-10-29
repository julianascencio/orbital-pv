"""
Earth-fixed ground track
========================

Convert a simple inclined circular orbit from an inertial frame to an
Earth-fixed longitude/latitude track while Earth rotates beneath it.

The example also demonstrates why antimeridian crossings must be split before
drawing ordinary 2D geographic lines.
"""

import matplotlib.pyplot as plt
import numpy as np

EARTH_RADIUS_KM = 6378.137
EARTH_MU_KM3_S2 = 398_600.4418
EARTH_ROTATION_RAD_S = 7.2921159e-5


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


altitude_km = 550.0
radius_km = EARTH_RADIUS_KM + altitude_km
period_s = 2.0 * np.pi * np.sqrt(radius_km**3 / EARTH_MU_KM3_S2)

time_s = np.linspace(0.0, 3.0 * period_s, 1800)
argument = 2.0 * np.pi * time_s / period_s
eci = orbit_xyz_km(radius_km, 51.6, 25.0, argument)

earth_angle = EARTH_ROTATION_RAD_S * time_s
cos_theta = np.cos(earth_angle)
sin_theta = np.sin(earth_angle)

x_ecef = cos_theta * eci[:, 0] + sin_theta * eci[:, 1]
y_ecef = -sin_theta * eci[:, 0] + cos_theta * eci[:, 1]
z_ecef = eci[:, 2]

longitude_deg = np.rad2deg(np.arctan2(y_ecef, x_ecef))
latitude_deg = np.rad2deg(np.arctan2(z_ecef, np.sqrt(x_ecef**2 + y_ecef**2)))

plot_longitude = longitude_deg.copy()
plot_latitude = latitude_deg.copy()
jumps = np.flatnonzero(np.abs(np.diff(longitude_deg)) > 180.0) + 1
plot_longitude[jumps] = np.nan
plot_latitude[jumps] = np.nan

fig, ax = plt.subplots(figsize=(10, 4.8))
ax.plot(plot_longitude, plot_latitude)
ax.set(xlim=(-180, 180), ylim=(-90, 90))
ax.set(xlabel="Longitude [deg]", ylabel="Latitude [deg]")
ax.set_title("Three-orbit Earth-fixed ground track")
ax.set_xticks(np.arange(-180, 181, 60))
ax.set_yticks(np.arange(-90, 91, 30))
ax.grid(True, alpha=0.3)
plt.show()
