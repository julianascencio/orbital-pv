"""Material-calibrated radiation dose and empirical remaining-power models.

These utilities integrate supplied spectra. They do not replace particle
transport, orbit environment models, or device irradiation measurements.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class RadiationExposure:
    """Integrated particle exposure for one species and material response."""

    transmitted_fluence_cm2: float
    displacement_damage_mev_g: float
    equivalent_fluence_cm2: float


@dataclass(frozen=True)
class RadiationResponse:
    """Fit parameters for R = 1 - C log10(1 + equivalent_fluence / Phi0).

    Parameters must come from a named technology/particle/reference-energy
    calibration; no universal spacecraft or perovskite default is supplied.
    """

    coefficient: float
    reference_fluence_cm2: float
    minimum_retention: float = 0.0

    def __post_init__(self) -> None:
        if not np.isfinite(self.coefficient) or self.coefficient < 0:
            raise ValueError("coefficient must be finite and non-negative")
        if not np.isfinite(self.reference_fluence_cm2) or self.reference_fluence_cm2 <= 0:
            raise ValueError("reference_fluence_cm2 must be finite and positive")
        if not np.isfinite(self.minimum_retention) or not 0 <= self.minimum_retention <= 1:
            raise ValueError("minimum_retention must lie in [0, 1]")


def radiation_equivalent_fluence(
    energy_mev: ArrayLike,
    differential_fluence_cm2_mev: ArrayLike,
    niel_mev_cm2_g: ArrayLike,
    *,
    reference_niel_mev_cm2_g: float,
    shielding_transmission: ArrayLike = 1.0,
) -> RadiationExposure:
    """Integrate differential particle fluence against a tabulated NIEL curve.

    Energy is MeV, differential fluence is particles/(cm² MeV), and NIEL is
    MeV cm²/g. The resulting displacement damage dose is MeV/g. Equivalent
    fluence divides that dose by the explicitly supplied reference NIEL.

    ``shielding_transmission`` is a dimensionless, energy-dependent transfer
    factor obtained externally. Simple attenuation omits energy redistribution,
    secondaries and angular transport; use a transported spectrum instead when
    those matter. Do not sum proton and electron equivalent fluences unless
    their material/reference normalization has been made compatible.
    """
    energy = np.asarray(energy_mev, dtype=float)
    if energy.ndim != 1 or len(energy) < 2 or not np.all(np.isfinite(energy)):
        raise ValueError("energy_mev must contain at least two finite energies")
    if np.any(energy <= 0) or np.any(np.diff(energy) <= 0):
        raise ValueError("energy_mev must be positive and strictly increasing")
    values = []
    for name, value in (
        ("differential_fluence_cm2_mev", differential_fluence_cm2_mev),
        ("niel_mev_cm2_g", niel_mev_cm2_g),
        ("shielding_transmission", shielding_transmission),
    ):
        try:
            array = np.broadcast_to(np.asarray(value, dtype=float), energy.shape)
        except ValueError as exc:
            raise ValueError(f"{name} must match the energy grid") from exc
        if not np.all(np.isfinite(array)) or np.any(array < 0):
            raise ValueError(f"{name} must be finite and non-negative")
        values.append(array)
    fluence, niel, transmission = values
    if np.any(transmission > 1):
        raise ValueError("shielding_transmission must lie in [0, 1]")
    if not np.isfinite(reference_niel_mev_cm2_g) or reference_niel_mev_cm2_g <= 0:
        raise ValueError("reference_niel_mev_cm2_g must be finite and positive")
    transmitted = fluence * transmission
    dose = float(np.trapezoid(transmitted * niel, energy))
    return RadiationExposure(
        transmitted_fluence_cm2=float(np.trapezoid(transmitted, energy)),
        displacement_damage_mev_g=dose,
        equivalent_fluence_cm2=dose / reference_niel_mev_cm2_g,
    )


def retained_power_fraction(
    equivalent_fluence_cm2: ArrayLike, response: RadiationResponse
) -> np.ndarray:
    """Return a bounded empirical remaining factor (zero exposure gives one).

    This monotone model does not describe annealing or perovskite self-healing.
    Extrapolation beyond the calibration fluence range requires validation.
    """
    fluence = np.asarray(equivalent_fluence_cm2, dtype=float)
    if not np.all(np.isfinite(fluence)) or np.any(fluence < 0):
        raise ValueError("equivalent fluence must be finite and non-negative")
    return np.clip(
        1 - response.coefficient * np.log10(1 + fluence / response.reference_fluence_cm2),
        response.minimum_retention,
        1.0,
    )
