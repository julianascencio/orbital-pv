"""Orbit and geometry helpers for the public OrbitalPV API."""

from __future__ import annotations

import numpy as np

from space_pv_core.constants import ASTRONOMICAL_UNIT_M, EARTH_EQUATORIAL_RADIUS_M
from space_pv_orbit import (
    SolarGeometry,
    body_vector_to_reference,
    cosine_incidence,
    earth_occultation_fraction,
    quaternion_wxyz_to_matrix,
    solar_geometry,
)

from space_pv_orbit.astropy_engine import geocentric_sun_positions_m
from space_pv_orbit.skyfield_engine import (
    propagate_geocentric_m,
    satellite_from_omm,
    satellite_from_tle,
)

EARTH_STANDARD_GRAVITATIONAL_PARAMETER_M3_S2 = 3.986004418e14
EARTH_ROTATION_RATE_RAD_S = 7.2921159e-5


def keplerian_orbit_positions_m(
    semi_major_axis_m: float,
    eccentricity: float,
    inclination_deg: float,
    *,
    raan_deg: float = 0.0,
    argument_of_periapsis_deg: float = 0.0,
    true_anomaly_rad: np.ndarray | None = None,
    samples: int = 721,
) -> np.ndarray:
    """Generate Keplerian ellipse positions in a simple ECI frame.

    This convenience helper is intended for deterministic examples and design
    visualization. Operational propagation should use OMM/TLE/SGP4 or SPICE.
    """
    if semi_major_axis_m <= 0.0:
        raise ValueError("semi_major_axis_m must be positive")
    if not 0.0 <= eccentricity < 1.0:
        raise ValueError("eccentricity must satisfy 0 <= e < 1")
    if samples < 2:
        raise ValueError("samples must be at least 2")

    anomaly = (
        np.linspace(0.0, 2.0 * np.pi, samples)
        if true_anomaly_rad is None
        else np.asarray(true_anomaly_rad, dtype=float)
    )
    p = semi_major_axis_m * (1.0 - eccentricity**2)
    radius = p / (1.0 + eccentricity * np.cos(anomaly))
    perifocal = np.column_stack(
        (radius * np.cos(anomaly), radius * np.sin(anomaly), np.zeros_like(radius))
    )

    inclination = np.deg2rad(inclination_deg)
    raan = np.deg2rad(raan_deg)
    argument = np.deg2rad(argument_of_periapsis_deg)
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
    return perifocal @ rotation.T


def circular_orbit_positions_m(
    altitude_m: float,
    inclination_deg: float,
    *,
    raan_deg: float = 0.0,
    argument_of_periapsis_deg: float = 0.0,
    samples: int = 721,
    earth_radius_m: float = EARTH_EQUATORIAL_RADIUS_M,
) -> np.ndarray:
    """Generate positions for a circular orbit at a fixed altitude."""
    if altitude_m < 0.0:
        raise ValueError("altitude_m must be non-negative")
    return keplerian_orbit_positions_m(
        earth_radius_m + altitude_m,
        0.0,
        inclination_deg,
        raan_deg=raan_deg,
        argument_of_periapsis_deg=argument_of_periapsis_deg,
        samples=samples,
    )


def ground_track_deg_from_eci(
    positions_m: np.ndarray,
    elapsed_seconds: np.ndarray,
    *,
    earth_rotation_rate_rad_s: float = EARTH_ROTATION_RATE_RAD_S,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert simple ECI positions to a spherical Earth-fixed ground track.

    The transform assumes a uniformly rotating spherical Earth and a zero
    Greenwich angle at elapsed time zero. Use Astropy/ITRS or SPICE for
    mission-grade frame transformations.
    """
    positions = np.asarray(positions_m, dtype=float)
    seconds = np.asarray(elapsed_seconds, dtype=float)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("positions_m must have shape (n, 3)")
    if seconds.ndim != 1 or len(seconds) != len(positions):
        raise ValueError("elapsed_seconds must have shape (n,) matching positions_m")

    theta = earth_rotation_rate_rad_s * seconds
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)
    x = cos_theta * positions[:, 0] + sin_theta * positions[:, 1]
    y = -sin_theta * positions[:, 0] + cos_theta * positions[:, 1]
    z = positions[:, 2]
    longitude_deg = np.rad2deg(np.arctan2(y, x))
    latitude_deg = np.rad2deg(np.arctan2(z, np.sqrt(x**2 + y**2)))
    return longitude_deg, latitude_deg


__all__ = [
    "ASTRONOMICAL_UNIT_M",
    "EARTH_EQUATORIAL_RADIUS_M",
    "EARTH_ROTATION_RATE_RAD_S",
    "EARTH_STANDARD_GRAVITATIONAL_PARAMETER_M3_S2",
    "SolarGeometry",
    "body_vector_to_reference",
    "circular_orbit_positions_m",
    "cosine_incidence",
    "earth_occultation_fraction",
    "geocentric_sun_positions_m",
    "ground_track_deg_from_eci",
    "keplerian_orbit_positions_m",
    "propagate_geocentric_m",
    "quaternion_wxyz_to_matrix",
    "satellite_from_omm",
    "satellite_from_tle",
    "solar_geometry",
]
