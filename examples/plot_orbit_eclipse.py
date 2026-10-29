"""
Eclipse fraction along a circular orbit
========================================

Use OrbitalPV's public orbit generator and occultation model to compute
illumination around a simple circular LEO orbit.
"""

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv

positions_m = opv.circular_orbit_positions_m(
    altitude_m=400_000.0,
    inclination_deg=0.0,
    samples=721,
)
sun_position_m = np.array([opv.ASTRONOMICAL_UNIT_M, 0.0, 0.0])
illumination = np.array(
    [opv.earth_occultation_fraction(position, sun_position_m) for position in positions_m]
)
orbit_angle_deg = np.linspace(0.0, 360.0, len(positions_m))

fig, ax = plt.subplots()
ax.plot(orbit_angle_deg, illumination)
ax.set(xlabel="Orbit angle [deg]", ylabel="Illumination fraction", ylim=(-0.05, 1.05))
ax.set_title("Earth occultation along a simple circular LEO orbit")
ax.grid(True, alpha=0.3)
plt.show()
