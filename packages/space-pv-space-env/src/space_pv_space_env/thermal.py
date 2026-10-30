"""Conservative, transient lumped thermal balance for a photovoltaic surface.

This is a screening model, not a finite-element spacecraft thermal solver. All
irradiances are already projected onto the receiving surface. Earth IR must not
be included in the photovoltaic irradiance. The radiation term is implicit,
avoiding the numerical instability of an explicit T**4 Euler step.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

STEFAN_BOLTZMANN = 5.670374419e-8


@dataclass(frozen=True)
class ThermalSurface:
    """Effective isothermal surface; areas in m² and heat capacity in J/K.

    ``radiating_area_m2`` includes every emitting face, while ``area_m2`` is
    the receiving/projected area associated with the supplied irradiance.
    Conductance couples the surface to a fixed-temperature spacecraft node.
    """

    area_m2: float = 1.0
    radiating_area_m2: float = 2.0
    heat_capacity_j_k: float = 10_000.0
    solar_absorptivity: float = 0.9
    ir_emissivity: float = 0.85
    conductance_w_k: float = 0.0
    bus_temperature_k: float = 293.15
    sink_temperature_k: float = 3.0

    def __post_init__(self) -> None:
        for name in ("area_m2", "radiating_area_m2", "heat_capacity_j_k"):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("solar_absorptivity", "ir_emissivity"):
            value = getattr(self, name)
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must lie in [0, 1]")
        for name in ("conductance_w_k", "bus_temperature_k", "sink_temperature_k"):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")


def _forcing(value: ArrayLike, size: int, name: str) -> np.ndarray:
    try:
        result = np.broadcast_to(np.asarray(value, dtype=float), (size,)).copy()
    except ValueError as exc:
        raise ValueError(f"{name} must be scalar or have one value per timestamp") from exc
    if not np.all(np.isfinite(result)) or np.any(result < 0):
        raise ValueError(f"{name} must be finite and non-negative")
    return result


def simulate_panel_thermal(
    time_s: ArrayLike,
    direct_solar_w_m2: ArrayLike,
    *,
    surface: ThermalSurface | None = None,
    albedo_w_m2: ArrayLike = 0.0,
    earth_ir_w_m2: ArrayLike = 0.0,
    internal_heat_w: ArrayLike = 0.0,
    pv_efficiency: ArrayLike = 0.25,
    efficiency_temperature_coefficient_per_k: float = -0.002,
    reference_temperature_k: float = 298.15,
    initial_temperature_k: float = 293.15,
    max_step_s: float = 30.0,
) -> pd.DataFrame:
    """Integrate a thermal/PV energy balance with auditable interval energies.

    For interval ``(time_s[i-1], time_s[i]]``, forcing at index ``i`` is
    piecewise constant. Efficiency is evaluated at each substep's starting
    temperature and clipped to [0, absorptivity]; radiative and conductive heat
    rejection are solved implicitly at its ending temperature. The temperature
    coefficient is a relative coefficient, e.g. -0.002 means -0.2 %/K.

    Albedo uses the same scalar PV efficiency as direct sunlight; a spectral
    model is needed where spectral differences matter. PV electricity is
    removed from this surface's thermal balance and is not destroyed: downstream
    payload/electronics heat belongs in the corresponding spacecraft node.
    """
    surface = surface or ThermalSurface()
    times = np.asarray(time_s, dtype=float)
    if times.ndim != 1 or len(times) < 2 or not np.all(np.isfinite(times)):
        raise ValueError("time_s must contain at least two finite timestamps")
    if np.any(np.diff(times) <= 0):
        raise ValueError("time_s must be strictly increasing")
    if not np.isfinite(initial_temperature_k) or initial_temperature_k <= 0:
        raise ValueError("initial_temperature_k must be positive")
    if not np.isfinite(max_step_s) or max_step_s <= 0:
        raise ValueError("max_step_s must be finite and positive")
    if not np.isfinite(reference_temperature_k) or reference_temperature_k <= 0:
        raise ValueError("reference_temperature_k must be positive")
    if not np.isfinite(efficiency_temperature_coefficient_per_k):
        raise ValueError("efficiency temperature coefficient must be finite")
    n = len(times)
    sunlight = _forcing(direct_solar_w_m2, n, "direct_solar_w_m2")
    albedo = _forcing(albedo_w_m2, n, "albedo_w_m2")
    earth_ir = _forcing(earth_ir_w_m2, n, "earth_ir_w_m2")
    internal = _forcing(internal_heat_w, n, "internal_heat_w")
    eta = _forcing(pv_efficiency, n, "pv_efficiency")
    if np.any(eta > surface.solar_absorptivity):
        raise ValueError("pv_efficiency cannot exceed solar absorptivity")
    incident = sunlight + albedo
    absorbed = (
        surface.area_m2 * (surface.solar_absorptivity * incident + surface.ir_emissivity * earth_ir)
        + internal
    )
    radiation = surface.ir_emissivity * STEFAN_BOLTZMANN * surface.radiating_area_m2
    temperatures = np.empty(n)
    temperatures[0] = initial_temperature_k
    input_energy = np.zeros(n)
    pv_energy = np.zeros(n)
    rejected_energy = np.zeros(n)

    def pv_power(index: int, temperature: float) -> float:
        efficiency = np.clip(
            eta[index]
            * (
                1
                + efficiency_temperature_coefficient_per_k * (temperature - reference_temperature_k)
            ),
            0.0,
            surface.solar_absorptivity,
        )
        return float(surface.area_m2 * incident[index] * efficiency)

    for i, interval in enumerate(np.diff(times), start=1):
        steps = int(np.ceil(interval / max_step_s))
        dt = interval / steps
        temperature = float(temperatures[i - 1])
        for _ in range(steps):
            electrical = pv_power(i, temperature)
            source = (
                absorbed[i]
                - electrical
                + radiation * surface.sink_temperature_k**4
                + surface.conductance_w_k * surface.bus_temperature_k
            )
            target = surface.heat_capacity_j_k / dt * temperature + source
            coefficient = surface.heat_capacity_j_k / dt + surface.conductance_w_k
            low, high = 0.0, max(temperature, target / coefficient, 1.0)
            # The implicit left side is monotone for nonnegative temperatures.
            for _ in range(64):
                middle = (low + high) / 2
                if coefficient * middle + radiation * middle**4 > target:
                    high = middle
                else:
                    low = middle
            temperature = (low + high) / 2
            rejected = radiation * (temperature**4 - surface.sink_temperature_k**4)
            rejected += surface.conductance_w_k * (temperature - surface.bus_temperature_k)
            input_energy[i] += absorbed[i] * dt
            pv_energy[i] += electrical * dt
            rejected_energy[i] += rejected * dt
        temperatures[i] = temperature
    stored_change = np.r_[0.0, surface.heat_capacity_j_k * np.diff(temperatures)]
    result = pd.DataFrame(
        {
            "time_s": times,
            "temperature_k": temperatures,
            "pv_power_w": [pv_power(i, float(t)) for i, t in enumerate(temperatures)],
            "absorbed_heat_w": absorbed,
            "interval_input_energy_j": input_energy,
            "interval_pv_energy_j": pv_energy,
            "interval_rejected_energy_j": rejected_energy,
            "interval_stored_energy_change_j": stored_change,
            "energy_balance_error_j": stored_change - input_energy + pv_energy + rejected_energy,
        }
    )
    result.attrs["model"] = "lumped semi-implicit thermal balance; projected irradiance inputs"
    return result
