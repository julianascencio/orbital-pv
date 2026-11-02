from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=1)
def _timescale():
    from skyfield.api import load

    return load.timescale(builtin=True)


def satellite_from_omm(fields: dict[str, object]):
    from skyfield.api import EarthSatellite

    return EarthSatellite.from_omm(_timescale(), fields)


def satellite_from_tle(line1: str, line2: str, *, name: str | None = None):
    from skyfield.api import EarthSatellite

    return EarthSatellite(line1, line2, name=name, ts=_timescale())


def propagate_geocentric_m(satellite, times: Sequence[datetime]) -> tuple[np.ndarray, np.ndarray]:
    t = _timescale().from_datetimes(list(times))
    state = satellite.at(t)
    return np.asarray(state.position.m, dtype=float).T, np.asarray(
        state.velocity.m_per_s, dtype=float
    ).T


def is_sunlit(
    satellite, times: Sequence[datetime], ephemeris_path: str = "de421.bsp"
) -> np.ndarray:
    from skyfield.api import load

    ts = load.timescale()
    t = ts.from_datetimes(list(times))
    eph = load(ephemeris_path)
    return np.asarray(satellite.at(t).is_sunlit(eph), dtype=bool)
