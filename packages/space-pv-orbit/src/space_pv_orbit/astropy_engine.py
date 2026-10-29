from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np


def geocentric_sun_positions_m(times: Sequence[datetime] | Sequence[str]) -> np.ndarray:
    """Geocentric GCRS Sun positions using Astropy's supported solar ephemeris path."""
    from astropy import units as u
    from astropy.coordinates import get_sun
    from astropy.time import Time

    sun = get_sun(Time(list(times)))
    xyz = sun.cartesian.xyz.to_value(u.m)
    return np.asarray(xyz, dtype=float).T
