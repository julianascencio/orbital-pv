"""Wavelength-resolved photocurrent and series-tandem current matching.

These methods integrate measured or modeled external quantum efficiency (EQE).
They do not infer a device's voltage, fill factor, or conversion efficiency.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

ELEMENTARY_CHARGE_C = 1.602176634e-19
PLANCK_J_S = 6.62607015e-34
LIGHT_SPEED_M_S = 299_792_458.0


def spectral_photocurrent_density(
    wavelength_nm: ArrayLike,
    spectral_irradiance_w_m2_nm: ArrayLike,
    eqe: ArrayLike,
) -> np.ndarray:
    """Integrate EQE times photon flux, returning photocurrent density in A/m².

    Wavelength is strictly increasing in nm and spectral irradiance is W/m²/nm.
    The final axis of irradiance/EQE must be wavelength; leading dimensions may
    be broadcast, allowing several spectra or devices. No interpolation or
    extrapolation is hidden inside this calculation. EQE must be in [0, 1].
    """
    wavelength = np.asarray(wavelength_nm, dtype=float)
    if wavelength.ndim != 1 or len(wavelength) < 2:
        raise ValueError("wavelength_nm must be a one-dimensional grid with at least two points")
    if not np.all(np.isfinite(wavelength)) or np.any(wavelength <= 0):
        raise ValueError("wavelength_nm must be finite and positive")
    if np.any(np.diff(wavelength) <= 0):
        raise ValueError("wavelength_nm must be strictly increasing")
    irradiance = np.asarray(spectral_irradiance_w_m2_nm, dtype=float)
    quantum_efficiency = np.asarray(eqe, dtype=float)
    for name, values in (("spectral irradiance", irradiance), ("EQE", quantum_efficiency)):
        if values.ndim == 0 or values.shape[-1] != len(wavelength):
            raise ValueError(f"{name}'s final dimension must match wavelength_nm")
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError(f"{name} must be finite and non-negative")
    if np.any(quantum_efficiency > 1):
        raise ValueError("EQE must lie in [0, 1]")
    try:
        absorbed = irradiance * quantum_efficiency
    except ValueError as exc:
        raise ValueError("irradiance and EQE dimensions are not broadcast compatible") from exc
    photon_current = ELEMENTARY_CHARGE_C * wavelength * 1e-9 / (PLANCK_J_S * LIGHT_SPEED_M_S)
    return np.asarray(np.trapezoid(absorbed * photon_current, wavelength, axis=-1))


@dataclass(frozen=True)
class TandemCurrent:
    """Current-matching result, not a power conversion efficiency estimate."""

    subcell_current_a_m2: np.ndarray
    series_current_a_m2: float
    current_mismatch_fraction: float


def tandem_current_density(
    wavelength_nm: ArrayLike,
    spectral_irradiance_w_m2_nm: ArrayLike,
    subcell_eqe: ArrayLike,
) -> TandemCurrent:
    """Calculate the limiting current of series-connected, equal-area subcells.

    Each EQE row is the *external* response of that subcell in the finished
    stack, referenced to the same incident spectrum. Their wavelength-wise sum
    cannot exceed one: using standalone EQEs without optical filtering would
    double count photons. Mismatch is a current-utilization metric, not a
    measured energy loss. Radiative coupling and carrier multiplication are
    outside this screening model.
    """
    eqe = np.asarray(subcell_eqe, dtype=float)
    if eqe.ndim != 2 or eqe.shape[0] < 2:
        raise ValueError("subcell_eqe must have at least two rows, one per subcell")
    if np.any(np.sum(eqe, axis=0) > 1 + 1e-10):
        raise ValueError("stack-referenced subcell EQEs cannot absorb the same photon twice")
    spectrum = np.asarray(spectral_irradiance_w_m2_nm, dtype=float)
    if spectrum.ndim != 1:
        raise ValueError("tandem_current_density expects one incident spectrum")
    currents = spectral_photocurrent_density(wavelength_nm, spectrum, eqe)
    limiting = float(np.min(currents))
    total = float(np.sum(currents))
    mismatch = 0.0 if total == 0 else 1 - len(currents) * limiting / total
    return TandemCurrent(currents, limiting, float(mismatch))
