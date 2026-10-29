"""
Earth-fixed ground track
========================

Generate an inclined circular orbit with OrbitalPV and transform it into a
simple Earth-fixed ground track through the public package API.
"""

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv

altitude_m = 550_000.0
radius_m = opv.EARTH_EQUATORIAL_RADIUS_M + altitude_m
period_s = 2.0 * np.pi * np.sqrt(
    radius_m**3 / opv.EARTH_STANDARD_GRAVITATIONAL_PARAMETER_M3_S2
)

time_s = np.linspace(0.0, 3.0 * period_s, 1800)
true_anomaly = 2.0 * np.pi * time_s / period_s
eci_m = opv.keplerian_orbit_positions_m(
    radius_m,
    0.0,
    inclination_deg=51.6,
    raan_deg=25.0,
    true_anomaly_rad=true_anomaly,
)
longitude_deg, latitude_deg = opv.ground_track_deg_from_eci(eci_m, time_s)

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
