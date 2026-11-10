"""Instantaneous cosine-law array pointing constraints at the regulated bus."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike


def pointing_power_envelope(
    normal_bus_w: ArrayLike,
    load_w: float,
    *,
    reserve_fraction: float = 0.2,
    offpoint_deg: float = 30.0,
) -> pd.DataFrame:
    """Screen sunlit, fixed-array pointing against a load plus reserve.

    ``normal_bus_w`` is a nonempty scalar or 1-D sequence of available bus power
    at normal incidence, in W, after distance and electrical/retention losses.
    Required power is ``load_w * (1 + reserve_fraction)``. The maximum angle
    between the array normal and Sun direction is acos(required/normal), in
    degrees. An infeasible normal-incidence state has a NaN angle, not zero.
    ``headroom_w`` is generation at ``offpoint_deg`` minus required power.

    This instantaneous cosine law assumes uniform, unshadowed illumination and
    constant electrical efficiency. It excludes eclipses, battery support,
    temperature response, gimbal limits and bus voltage constraints. A reserve
    fraction is an engineering assumption, not a probabilistic confidence bound.
    """
    normal = np.atleast_1d(np.asarray(normal_bus_w, dtype=float))
    if normal.ndim != 1 or normal.size == 0 or not np.isfinite(normal).all():
        raise ValueError("normal_bus_w must be a nonempty finite scalar or 1-D array")
    if (normal < 0).any():
        raise ValueError("normal_bus_w must be nonnegative")
    if not np.isfinite(load_w) or load_w <= 0:
        raise ValueError("load_w must be finite and positive")
    if not np.isfinite(reserve_fraction) or reserve_fraction < 0:
        raise ValueError("reserve_fraction must be finite and nonnegative")
    if not np.isfinite(offpoint_deg) or not 0 <= offpoint_deg <= 90:
        raise ValueError("offpoint_deg must be between 0 and 90 degrees")
    required = load_w * (1 + reserve_fraction)
    if not np.isfinite(required):
        raise ValueError("required bus power must be finite")
    feasible = normal >= required
    angle = np.full(normal.shape, np.nan)
    angle[feasible] = np.rad2deg(np.arccos(np.clip(required / normal[feasible], 0, 1)))
    at_angle = normal * np.cos(np.deg2rad(offpoint_deg))
    if offpoint_deg == 90:
        at_angle[:] = 0.0
    return pd.DataFrame(
        {
            "normal_bus_w": normal,
            "required_bus_w": required,
            "normal_feasible": feasible,
            "max_offpoint_deg": angle,
            "offpoint_bus_w": at_angle,
            "headroom_w": at_angle - required,
            "offpoint_feasible": at_angle >= required,
        }
    )
