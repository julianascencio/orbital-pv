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
_EARTH_J2 = 1.08262668e-3
_TROPICAL_YEAR_S = 365.2422 * 86_400.0


def circular_orbit_period_s(altitude_m: float) -> float:
    """Return the two-body period of a circular Earth orbit in seconds.

    ``altitude_m`` is a finite, positive height above the equatorial Earth
    radius. This is a design estimate, without perturbations or station keeping.
    """
    if not np.isfinite(altitude_m) or altitude_m <= 0.0:
        raise ValueError("altitude_m must be finite and positive")
    radius = EARTH_EQUATORIAL_RADIUS_M + altitude_m
    return float(2.0 * np.pi * np.sqrt(radius**3 / EARTH_STANDARD_GRAVITATIONAL_PARAMETER_M3_S2))


def sun_synchronous_inclination_deg(altitude_m: float) -> float:
    """Estimate circular sun-synchronous inclination from first-order J2.

    Match ``-1.5 * J2 * n * (R/a)**2 * cos(i)`` to one eastward node
    revolution per 365.2422-day tropical year. The result is a mean-element
    design approximation; it omits higher harmonics, drag and short-period
    effects. It does not imply uninterrupted sunlight.

    Raises ``ValueError`` when altitude is invalid or J2 alone cannot provide
    the required precession at that altitude.
    """
    period = circular_orbit_period_s(altitude_m)
    radius = EARTH_EQUATORIAL_RADIUS_M + altitude_m
    mean_motion = 2.0 * np.pi / period
    node_rate = 2.0 * np.pi / _TROPICAL_YEAR_S
    cos_inclination = -node_rate / (
        1.5 * _EARTH_J2 * mean_motion * (EARTH_EQUATORIAL_RADIUS_M / radius) ** 2
    )
    if abs(cos_inclination) > 1.0:
        raise ValueError("No first-order J2 sun-synchronous solution at this altitude")
    return float(np.rad2deg(np.arccos(cos_inclination)))


def raan_from_local_solar_time_deg(
    local_time_hours: float,
    *,
    sun_right_ascension_deg: float = 0.0,
    ascending: bool = True,
) -> float:
    """Convert local solar time at an equator crossing to RAAN in degrees.

    Hours must be in ``[0, 24)``. Set ``ascending=False`` for a descending
    crossing. The returned ascending-node angle is wrapped to ``[0, 360)``.
    Supply the *mean* Sun's right ascension for mean local solar time, or the
    physical Sun's right ascension for apparent local solar time. These differ
    by the equation of time and must not be silently interchanged.

    This sets the plane at one epoch; it does not propagate nodal precession.
    """
    if not np.isfinite(local_time_hours) or not 0.0 <= local_time_hours < 24.0:
        raise ValueError("local_time_hours must be finite and in [0, 24)")
    if not np.isfinite(sun_right_ascension_deg):
        raise ValueError("sun_right_ascension_deg must be finite")
    node_offset = 0.0 if ascending else 180.0
    return float((sun_right_ascension_deg + 15.0 * (local_time_hours - 12.0) + node_offset) % 360.0)


def circular_eclipse_duration_s(
    altitude_m: float, beta_angle_deg: float | np.ndarray
) -> np.ndarray:
    """Estimate eclipse duration per circular orbit with a cylindrical shadow.

    ``beta_angle_deg`` is the signed angle between the Earth-to-Sun direction
    and the orbital plane, in ``[-90, 90]``. Returns seconds as an array with
    the input beta shape (a zero-dimensional array for a scalar).

    A spherical Earth and a point Sun at infinite distance are assumed. The
    eclipse half-angle is ``acos(sqrt(1 - (R/a)**2) / cos(beta))`` below the
    critical beta ``asin(R/a)``; above it the duration is zero. Finite solar
    radius, penumbra, atmosphere and oblateness are omitted. In particular,
    zero here is not proof of uninterrupted full sunlight: use
    :func:`earth_occultation_fraction` for a finite-Sun geometry check.

    See NASA's spacecraft thermal-environment course, slides 110-119:
    https://ntrs.nasa.gov/api/citations/20200007746/downloads/20200007746.pdf
    """
    period = circular_orbit_period_s(altitude_m)
    beta = np.asarray(beta_angle_deg, dtype=float)
    if not np.all(np.isfinite(beta)) or np.any(np.abs(beta) > 90.0):
        raise ValueError("beta_angle_deg must be finite and in [-90, 90]")
    radius_ratio = EARTH_EQUATORIAL_RADIUS_M / (EARTH_EQUATORIAL_RADIUS_M + altitude_m)
    critical_beta = np.rad2deg(np.arcsin(radius_ratio))
    cosine_half_angle = np.sqrt(1.0 - radius_ratio**2) / np.cos(np.deg2rad(beta))
    half_angle = np.arccos(np.clip(cosine_half_angle, 0.0, 1.0))
    return np.where(np.abs(beta) >= critical_beta, 0.0, period * half_angle / np.pi)


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
    "circular_eclipse_duration_s",
    "circular_orbit_period_s",
    "circular_orbit_positions_m",
    "cosine_incidence",
    "earth_occultation_fraction",
    "geocentric_sun_positions_m",
    "ground_track_deg_from_eci",
    "keplerian_orbit_positions_m",
    "propagate_geocentric_m",
    "quaternion_wxyz_to_matrix",
    "raan_from_local_solar_time_deg",
    "satellite_from_omm",
    "satellite_from_tle",
    "solar_geometry",
    "sun_synchronous_inclination_deg",
]
