from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from space_pv_core.constants import SOLAR_CONSTANT_W_M2


@dataclass(frozen=True, slots=True)
class PvwattsReference:
    """Calibrated BOL DC reference for a spacecraft panel/array.

    `pdc0_w` is defined at `reference_irradiance_w_m2` and `reference_temperature_c`.
    For space PV, this is intentionally a calibration contract instead of assuming a
    terrestrial STC reference is physically meaningful for every cell technology.
    """

    pdc0_w: float
    gamma_pdc_per_c: float
    reference_irradiance_w_m2: float = SOLAR_CONSTANT_W_M2
    reference_temperature_c: float = 25.0


def effective_irradiance_w_m2(
    am0_irradiance_w_m2: float | np.ndarray,
    illumination_fraction: float | np.ndarray,
    cosine_aoi: float | np.ndarray,
    *,
    spectral_factor: float | np.ndarray = 1.0,
    optical_factor: float | np.ndarray = 1.0,
) -> np.ndarray:
    """Convert space environment/geometry state into cell-effective irradiance."""
    return (
        np.asarray(am0_irradiance_w_m2, dtype=float)
        * np.clip(np.asarray(illumination_fraction, dtype=float), 0.0, 1.0)
        * np.clip(np.asarray(cosine_aoi, dtype=float), 0.0, 1.0)
        * np.asarray(spectral_factor, dtype=float)
        * np.asarray(optical_factor, dtype=float)
    )


def pvwatts_dc_space(
    effective_irradiance: float | np.ndarray,
    cell_temperature_c: float | np.ndarray,
    reference: PvwattsReference,
) -> np.ndarray:
    """Use pvlib's PVWatts DC equation with an explicit space reference irradiance.

    This is a calibrated engineering baseline, not a multi-junction radiation model.
    """
    import pvlib

    irradiance = np.asarray(effective_irradiance, dtype=float)
    temperature = np.asarray(cell_temperature_c, dtype=float)
    equivalent_stc = irradiance / reference.reference_irradiance_w_m2 * 1000.0
    return np.asarray(
        pvlib.pvsystem.pvwatts_dc(
            equivalent_stc,
            temperature,
            reference.pdc0_w,
            reference.gamma_pdc_per_c,
            temp_ref=reference.reference_temperature_c,
        ),
        dtype=float,
    )
