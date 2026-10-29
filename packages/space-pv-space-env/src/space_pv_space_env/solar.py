from __future__ import annotations

import numpy as np

from space_pv_core.constants import ASTRONOMICAL_UNIT_M, SOLAR_CONSTANT_W_M2


def am0_irradiance(distance_to_sun_m: float | np.ndarray) -> float | np.ndarray:
    distance = np.asarray(distance_to_sun_m, dtype=float)
    result = SOLAR_CONSTANT_W_M2 * (ASTRONOMICAL_UNIT_M / distance) ** 2
    return float(result) if result.ndim == 0 else result


def incidence_factor(cosine_aoi: float | np.ndarray, illuminated: bool | np.ndarray = True):
    cos_aoi = np.clip(np.asarray(cosine_aoi, dtype=float), 0.0, 1.0)
    lit = np.asarray(illuminated, dtype=bool)
    result = cos_aoi * lit
    return float(result) if result.ndim == 0 else result
