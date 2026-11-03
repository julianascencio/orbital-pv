"""Mars seasonal geometry from NASA GISS Mars24 (Allison & McEwen, 2000).

Implements the corrected 2025-01-07 algorithm, sections B and D1/D2.
https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
Input is Julian date in TT, never an implicit UTC/mission-sol conversion.
"""

from __future__ import annotations

import numpy as np

MARS_SOL_SECONDS = 86400.0 * 1.0274912517


def mars_solar_parameters(julian_date_tt: float | np.ndarray) -> dict[str, np.ndarray]:
    """Return solar longitude, declination and Sun distance for TT Julian dates.

    Angles are degrees; declination is planetographic as in Mars24. This is
    an analytic seasonal approximation, not a SPICE ephemeris. Use Astropy's
    ``Time(..., scale='utc').tt.jd`` for leap-second-aware UTC conversion.
    """
    jd = np.asarray(julian_date_tt, dtype=float)
    if not np.all(np.isfinite(jd)):
        raise ValueError("julian_date_tt must be finite")
    d = jd - 2451545.0
    m = np.deg2rad(19.3871 + 0.52402073 * d)
    pbs = np.zeros_like(d)
    for amplitude, period, phase in (
        (0.0071, 2.2353, 49.409),
        (0.0057, 2.7543, 168.173),
        (0.0039, 1.1177, 191.837),
        (0.0037, 15.7866, 21.736),
        (0.0021, 2.1354, 15.704),
        (0.0020, 2.4694, 95.528),
        (0.0018, 32.8493, 49.095),
    ):
        pbs += amplitude * np.cos(np.deg2rad(0.985626 * d / period + phase))
    center = (
        (10.691 + 3e-7 * d) * np.sin(m)
        + 0.623 * np.sin(2 * m)
        + 0.050 * np.sin(3 * m)
        + 0.005 * np.sin(4 * m)
        + 0.0005 * np.sin(5 * m)
        + pbs
    )
    ls = (270.3871 + 0.524038496 * d + center) % 360.0
    distance = 1.52367934 * (
        1.00436
        - 0.09309 * np.cos(m)
        - 0.004336 * np.cos(2 * m)
        - 0.00031 * np.cos(3 * m)
        - 0.00003 * np.cos(4 * m)
    )
    return {
        "solar_longitude_deg": ls,
        "declination_deg": mars_declination(ls),
        "sun_distance_au": distance,
    }


def mars_declination(solar_longitude_deg: float | np.ndarray) -> np.ndarray:
    """Mars24 planetographic solar declination in degrees from season Ls."""
    ls = np.asarray(solar_longitude_deg, dtype=float)
    if not np.all(np.isfinite(ls)):
        raise ValueError("solar_longitude_deg must be finite")
    sine = np.sin(np.deg2rad(ls))
    return np.rad2deg(np.arcsin(0.42565 * sine)) + 0.25 * sine
