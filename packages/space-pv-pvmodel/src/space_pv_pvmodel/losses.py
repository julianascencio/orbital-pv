"""Explicit sequential power stages for a calibrated spacecraft PV baseline."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from .model import PvwattsReference, pvwatts_dc_space

type NumericInput = ArrayLike | pd.Series


def _finite_array(name: str, value: NumericInput) -> np.ndarray:
    """Coerce real numerical values without losing a dimension or missing value."""
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or (
            raw.dtype.kind == "O"
            and any(isinstance(item, (complex, np.complexfloating)) for item in raw.flat)
        ):
            raise ValueError(f"{name} must contain real values")
        array = (
            value.to_numpy(dtype=float, na_value=np.nan)
            if isinstance(value, pd.Series)
            else np.asarray(value, dtype=float)
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain finite real numeric values") from error
    if array.ndim > 1 or array.size == 0:
        raise ValueError(f"{name} must be a scalar or a nonempty one-dimensional input")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return np.atleast_1d(array)


def _reference_value(name: str, value: float) -> float:
    if np.ndim(value) != 0:
        raise ValueError(f"reference.{name} must be a scalar")
    return float(_finite_array(f"reference.{name}", value)[0])


def pvwatts_loss_chain(
    reference: PvwattsReference,
    *,
    am0_irradiance_w_m2: NumericInput = 1361.0,
    illumination_fraction: NumericInput = 1.0,
    cosine_aoi: NumericInput = 1.0,
    spectral_factor: NumericInput = 1.0,
    optical_factor: NumericInput = 1.0,
    cell_temperature_c: NumericInput = 25.0,
    degradation_factor: NumericInput = 1.0,
    mismatch_factor: NumericInput = 1.0,
    wiring_efficiency: NumericInput = 1.0,
    conversion_efficiency: NumericInput = 1.0,
    power_limit_w: NumericInput | None = None,
    availability_factor: NumericInput = 1.0,
    curtailment_factor: NumericInput = 1.0,
) -> pd.DataFrame:
    """Return a transparent sequence of modeled PV power stages, in watts.

    ``reference`` specifies beginning-of-life (BOL) array DC power at its
    reference irradiance and cell temperature. That calibration already
    includes inherent cell and coverglass efficiencies: ``optical_factor``
    represents an *additional* transmission factor relative to that reference,
    not another multiplication by the cell efficiency or BOL coverglass loss.

    Inputs are finite scalars or nonempty one-dimensional arrays. Scalars and
    length-one arrays broadcast to the common sample count. Pandas Series must
    have identical indexes; their shared index is preserved, without sorting
    or label alignment. An indexed length-one Series cannot be broadcast onto
    a larger positional array. With no Series inputs, use a RangeIndex.

    AM0 irradiance and ``reference.pdc0_w`` must be nonnegative; reference
    irradiance must be positive. All fractional inputs are in [0, 1], except
    ``spectral_factor``, which must be positive and may exceed one. The
    temperature multiplier ``1 + gamma * (Tcell - Tref)`` may produce a gain
    but cannot be negative. Values outside these domains are rejected rather
    than clipped. Zero irradiance, full eclipse and zero available power are
    valid. ``power_limit_w=None`` disables clipping; a finite nonnegative
    scalar or per-sample limit caps power *after* electrical conversion.

    The returned columns, in sequence, are ``reference_power_w``,
    ``after_irradiance_w``, ``after_eclipse_w``, ``after_pointing_w``,
    ``after_spectral_w``, ``after_optical_w``, ``after_temperature_w``,
    ``after_degradation_w``, ``after_mismatch_w``, ``after_wiring_w``,
    ``after_conversion_w``, ``after_clipping_w``, ``after_availability_w``,
    and ``modeled_power_w`` (after curtailment). The temperature stage calls
    :func:`pvwatts_dc_space` with the accumulated effective irradiance.

    Through ``after_wiring_w``, power is on the array DC side. Conversion is a
    generic DC/DC or other chosen electronics boundary; it does not imply a
    terrestrial AC inverter. The cap, availability and curtailment apply on
    that output side. Compare measurements at the same electrical boundary.
    Battery storage, spacecraft loads and converter standby consumption are
    not modeled. Set post-array factors to one and omit the cap for an array
    DC-only comparison.

    Factors are supplied assumptions or independently established states,
    not inferred diagnoses. Differences between consecutive stages provide
    an order-dependent accounting, not unique causal attribution. Irradiance,
    spectral and temperature changes can create signed gains relative to the
    reference. This is the existing calibrated PVWatts engineering baseline,
    not a multi-junction spectral or radiation-damage model.

    See Also
    --------
    pvwatts_dc_space : PVWatts DC equation with a space irradiance reference.

    References
    ----------
    * pvlib PVWatts DC model:
      https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.pvwatts_dc.html
    * NASA Small Spacecraft Technology, Power:
      https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/
    """
    if not isinstance(reference, PvwattsReference):
        raise TypeError("reference must be a PvwattsReference")
    pdc0_w = _reference_value("pdc0_w", reference.pdc0_w)
    reference_irradiance = _reference_value(
        "reference_irradiance_w_m2", reference.reference_irradiance_w_m2
    )
    reference_temperature = _reference_value(
        "reference_temperature_c", reference.reference_temperature_c
    )
    gamma = _reference_value("gamma_pdc_per_c", reference.gamma_pdc_per_c)
    if pdc0_w < 0:
        raise ValueError("reference.pdc0_w must be nonnegative")
    if reference_irradiance <= 0:
        raise ValueError("reference.reference_irradiance_w_m2 must be positive")
    validated_reference = PvwattsReference(
        pdc0_w, gamma, reference_irradiance, reference_temperature
    )

    inputs = {
        "am0_irradiance_w_m2": am0_irradiance_w_m2,
        "illumination_fraction": illumination_fraction,
        "cosine_aoi": cosine_aoi,
        "spectral_factor": spectral_factor,
        "optical_factor": optical_factor,
        "cell_temperature_c": cell_temperature_c,
        "degradation_factor": degradation_factor,
        "mismatch_factor": mismatch_factor,
        "wiring_efficiency": wiring_efficiency,
        "conversion_efficiency": conversion_efficiency,
        "availability_factor": availability_factor,
        "curtailment_factor": curtailment_factor,
    }
    if power_limit_w is not None:
        inputs["power_limit_w"] = power_limit_w
    index = None
    for name, value in inputs.items():
        if isinstance(value, pd.Series):
            if index is None:
                index = value.index
            elif not index.equals(value.index):
                raise ValueError(f"{name}: all pandas Series inputs must have identical indexes")
    arrays = {name: _finite_array(name, value) for name, value in inputs.items()}
    size = max(array.size for array in arrays.values())
    if any(array.size not in (1, size) for array in arrays.values()):
        raise ValueError("inputs must broadcast to one common one-dimensional sample count")
    if index is not None and len(index) != size:
        raise ValueError("a pandas Series index must match the broadcast sample count")
    arrays = {name: np.broadcast_to(array, (size,)) for name, array in arrays.items()}
    for name, values in arrays.items():
        if name in ("am0_irradiance_w_m2", "power_limit_w"):
            if (values < 0).any():
                raise ValueError(f"{name} must be nonnegative")
        elif name == "spectral_factor":
            if (values <= 0).any():
                raise ValueError("spectral_factor must be positive")
        elif name != "cell_temperature_c" and ((values < 0) | (values > 1)).any():
            raise ValueError(f"{name} must be in [0, 1]")

    with np.errstate(over="ignore", invalid="ignore"):
        thermal_factor = 1.0 + gamma * (arrays["cell_temperature_c"] - reference_temperature)
    if not np.isfinite(thermal_factor).all() or (thermal_factor < 0).any():
        raise ValueError("temperature multiplier must be finite and nonnegative")

    # Reuse the existing DC equation rather than introduce a second version.
    # The earlier columns make its multiplicative inputs separately inspectable.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        stages = {"reference_power_w": np.full(size, pdc0_w)}
        power = pdc0_w * (arrays["am0_irradiance_w_m2"] / reference_irradiance)
        stages["after_irradiance_w"] = power
        effective_irradiance = arrays["am0_irradiance_w_m2"].copy()
        for factor, column in (
            ("illumination_fraction", "after_eclipse_w"),
            ("cosine_aoi", "after_pointing_w"),
            ("spectral_factor", "after_spectral_w"),
            ("optical_factor", "after_optical_w"),
        ):
            power = power * arrays[factor]
            effective_irradiance = effective_irradiance * arrays[factor]
            stages[column] = power
        power = pvwatts_dc_space(
            effective_irradiance, arrays["cell_temperature_c"], validated_reference
        )
        stages["after_temperature_w"] = power
        for factor, column in (
            ("degradation_factor", "after_degradation_w"),
            ("mismatch_factor", "after_mismatch_w"),
            ("wiring_efficiency", "after_wiring_w"),
            ("conversion_efficiency", "after_conversion_w"),
        ):
            power = power * arrays[factor]
            stages[column] = power
        if power_limit_w is not None:
            power = np.minimum(power, arrays["power_limit_w"])
        stages["after_clipping_w"] = power
        power = power * arrays["availability_factor"]
        stages["after_availability_w"] = power
        stages["modeled_power_w"] = power * arrays["curtailment_factor"]

    frame = pd.DataFrame(stages, index=index)
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("inputs produce nonfinite stage power; check magnitudes and reference")
    return frame
