"""
Eclipse fraction along a circular orbit
========================================

This example uses the geometric Earth/Sun occultation model to show how
illumination changes around a simple circular LEO orbit.
"""

import matplotlib.pyplot as plt
import numpy as np

from space_pv_core.constants import ASTRONOMICAL_UNIT_M, EARTH_EQUATORIAL_RADIUS_M
from space_pv_orbit.geometry import earth_occultation_fraction

altitude_m = 550_000.0
radius_m = EARTH_EQUATORIAL_RADIUS_M + altitude_m
angle_deg = np.linspace(0.0, 360.0, 721)
angle_rad = np.deg2rad(angle_deg)

spacecraft = np.column_stack(
    (radius_m * np.cos(angle_rad), radius_m * np.sin(angle_rad), np.zeros_like(angle_rad))
)
sun = np.array([ASTRONOMICAL_UNIT_M, 0.0, 0.0])

illumination = np.array([earth_occultation_fraction(position, sun) for position in spacecraft])

fig, ax = plt.subplots()
ax.plot(angle_deg, illumination)
ax.set(xlabel="Orbit angle [deg]", ylabel="Illumination fraction", ylim=(-0.05, 1.05))
ax.set_title("Earth occultation along a simple circular LEO orbit")
ax.grid(True, alpha=0.3)
plt.show()
