"""Lunar PV screening, explicit thermal forcing and storage design sweeps."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from space_pv_space_env.lunar import solar_disc_visibility
from space_pv_space_env.thermal import STEFAN_BOLTZMANN, ThermalSurface, simulate_panel_thermal

from .eps import BatterySpec, dispatch_power
from .model import PvwattsReference, pvwatts_dc_space


def _positive(value: float, name: str, *, zero: bool = False) -> None:
    if not np.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'non-negative' if zero else 'positive'}")


def _series(value: ArrayLike, n: int, name: str) -> np.ndarray:
    a = np.broadcast_to(np.asarray(value, dtype=float), (n,)).copy()
    if not np.isfinite(a).all():
        raise ValueError(f"{name} must be finite")
    return a


def lunar_pv_power(
    geometry: pd.DataFrame,
    horizon: pd.DataFrame,
    *,
    reference: PvwattsReference,
    cell_temperature_c: ArrayLike,
    mode: Literal["fixed", "azimuth_tracking", "sun_tracking"] = "fixed",
    tilt_deg: float = 90.0,
    panel_azimuth_deg: float = 0.0,
    optical_retention: ArrayLike = 1.0,
) -> pd.DataFrame:
    """Project direct AM0 radiation and reuse the calibrated PVWatts baseline.

    Tilt is from horizontal, azimuth clockwise from true north. Azimuth tracking
    keeps the selected tilt; sun tracking follows the centre of the Sun in two
    axes (including small negative elevations from elevated sites). No sky
    diffuse, ground-reflected light, self-shading, tracker power, degradation or
    spectral correction is implicit. Optical retention is a supplied scenario.
    Earth/terrain visibility fractions are multiplied: their simultaneous
    overlap is approximate. Disc area visibility uses centre-ray incidence.
    """
    if mode not in {"fixed", "azimuth_tracking", "sun_tracking"}:
        raise ValueError("Unknown tracking mode")
    if not np.isfinite([tilt_deg, panel_azimuth_deg]).all() or not 0 <= tilt_deg <= 180:
        raise ValueError("Finite angles and tilt in [0,180] required")
    required = [
        "azimuth_deg",
        "elevation_deg",
        "solar_angular_radius_deg",
        "earth_visible_fraction",
        "unobstructed_dni_w_m2",
    ]
    values = geometry[required].to_numpy(dtype=float)
    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("Geometry must contain finite, nonempty data")
    az, el, radius, earth, dni = values.T
    if np.any((earth < 0) | (earth > 1)) or np.any(dni < 0):
        raise ValueError("Invalid eclipse fraction or irradiance")
    n = len(horizon)
    expected_az = (np.arange(n) + 0.5) * 360 / max(n, 1)
    if n < 4 or not np.allclose(horizon.azimuth_deg, expected_az):
        raise ValueError("Horizon must use complete, regular sector centres")
    angles = horizon.horizon_elevation_deg.to_numpy(dtype=float)
    if not np.isfinite(angles).all() or np.any(np.abs(angles) > 90):
        raise ValueError("Invalid horizon angles")
    sector = np.minimum((np.mod(az, 360) / 360 * n).astype(int), n - 1)
    skyline = angles[sector]
    visible = solar_disc_visibility(el, skyline, radius)
    if mode == "sun_tracking":
        incidence = np.ones(len(geometry))
    else:
        delta = (
            np.zeros(len(az)) if mode == "azimuth_tracking" else np.deg2rad(az - panel_azimuth_deg)
        )
        beta = np.deg2rad(tilt_deg)
        incidence = np.maximum(
            0,
            np.sin(np.deg2rad(el)) * np.cos(beta)
            + np.cos(np.deg2rad(el)) * np.sin(beta) * np.cos(delta),
        )
    retention = _series(optical_retention, len(geometry), "optical_retention")
    temperature = _series(cell_temperature_c, len(geometry), "cell_temperature_c")
    if np.any((retention < 0) | (retention > 1)) or np.any(temperature <= -273.15):
        raise ValueError("Retention must be in [0,1] and temperature above absolute zero")
    _positive(reference.pdc0_w, "reference power")
    _positive(reference.reference_irradiance_w_m2, "reference irradiance")
    if not np.isfinite([reference.gamma_pdc_per_c, reference.reference_temperature_c]).all():
        raise ValueError("Reference must be finite")
    if np.any(
        1 + reference.gamma_pdc_per_c * (temperature - reference.reference_temperature_c) < 0
    ):
        raise ValueError("Temperature correction would yield negative power")
    poa = dni * earth * visible * incidence * retention
    result = geometry.copy()
    result["horizon_elevation_deg"] = skyline
    result["terrain_visible_fraction"] = visible
    result["cosine_incidence"] = incidence
    result["poa_direct_w_m2"] = poa
    result["cell_temperature_c"] = temperature
    result["dc_power_w"] = pvwatts_dc_space(poa, temperature, reference)
    result.attrs.update(mode=mode, model="direct AM0; sector horizon; calibrated scalar PVWatts")
    return result


def lunar_panel_thermal(
    time_s: ArrayLike,
    poa_direct_w_m2: ArrayLike,
    *,
    ground_temperature_k: ArrayLike,
    ground_view_factor: float,
    ground_emissivity: float = 0.95,
    surface: ThermalSurface | None = None,
    **thermal_options,
) -> pd.DataFrame:
    """Reuse the vacuum thermal balance with explicit lunar ground IR.

    View factor is averaged over *all emitting panel faces*. Multiplication by
    radiating_area/receiving_area converts it to the existing solver's receiving
    area convention. For bolometric brightness temperature (Diviner), set
    ``ground_emissivity=1`` because emissivity is already encoded in radiance.
    For physical ground temperature, supply its emissivity. Ground-reflected
    background IR is neglected. Surface temperatures are environmental
    boundary values, not cell temperatures. Direct forcing and ground values at
    index i apply to (time[i-1], time[i]]; the first sample initializes the model.
    """
    surface = surface or ThermalSurface()
    for name, value in (
        ("ground_view_factor", ground_view_factor),
        ("ground_emissivity", ground_emissivity),
    ):
        if not np.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be in [0,1]")
    temperature = _series(ground_temperature_k, len(np.asarray(time_s)), "ground_temperature_k")
    if np.any(temperature <= 0):
        raise ValueError("Ground temperature must be positive Kelvin")
    ground_ir = (
        surface.radiating_area_m2
        / surface.area_m2
        * ground_view_factor
        * ground_emissivity
        * STEFAN_BOLTZMANN
        * temperature**4
    )
    # Restrict the existing solver's uniform background term to the sky-facing
    # fraction. Ground irradiance is then added once, in its receiving-area units.
    surface = replace(
        surface, sink_temperature_k=surface.sink_temperature_k * (1 - ground_view_factor) ** 0.25
    )
    result = simulate_panel_thermal(
        time_s, poa_direct_w_m2, surface=surface, earth_ir_w_m2=ground_ir, **thermal_options
    )
    result["ground_temperature_k"] = temperature
    result["ground_ir_on_receiving_area_w_m2"] = ground_ir
    result.attrs["environment"] = "lunar ground IR; vacuum; no convective cooling"
    return result


def survival_heater_power(
    sink_temperature_k: ArrayLike,
    *,
    setpoint_k: float,
    thermal_conductance_w_k: float,
    internal_heat_w: ArrayLike = 0.0,
) -> np.ndarray:
    """Steady equivalent-conductance heater demand, max(UA*(Tset-Tsink)-Q,0).

    UA is a user-supplied effective thermal-loss coefficient, not lunar air
    convection. This screening relation omits thermal mass and must not be
    confused with the separate nonlinear panel thermal model.
    """
    _positive(setpoint_k, "setpoint_k")
    _positive(thermal_conductance_w_k, "thermal_conductance_w_k", zero=True)
    t, q = np.broadcast_arrays(
        np.asarray(sink_temperature_k, dtype=float), np.asarray(internal_heat_w, dtype=float)
    )
    if not np.isfinite(t).all() or not np.isfinite(q).all() or np.any(t <= 0) or np.any(q < 0):
        raise ValueError("Positive Kelvin and non-negative finite internal heat required")
    return np.maximum(thermal_conductance_w_k * (setpoint_k - t) - q, 0)


def longest_darkness_hours(
    time_s: ArrayLike, visible_fraction: ArrayLike, *, threshold: float = 0.01
) -> float:
    """Longest contiguous low-visibility interval; no wraparound is assumed.

    Times are N+1 boundaries and visibility has N interval values. Results are
    censored by the simulation start/end, and resolved only at the supplied step.
    """
    t = np.asarray(time_s, dtype=float)
    if t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError("Require increasing finite interval boundaries")
    v = _series(visible_fraction, len(t) - 1, "visible_fraction")
    if not np.isfinite(threshold) or not 0 <= threshold <= 1 or np.any((v < 0) | (v > 1)):
        raise ValueError("Visibility and threshold must be in [0,1]")
    longest = current = 0.0
    for dt, fraction in zip(np.diff(t), v, strict=True):
        current = current + float(dt) if fraction <= threshold else 0.0
        longest = max(longest, current)
    return longest / 3600


def size_lunar_storage(
    time_s: ArrayLike,
    generation_per_m2_w: ArrayLike,
    demand_w: ArrayLike,
    *,
    array_areas_m2: ArrayLike,
    capacities_wh: ArrayLike,
    battery_template: BatterySpec,
    array_mass_kg_m2: float = 3.0,
    battery_specific_energy_wh_kg: float = 150.0,
    require_terminal_soc: bool = True,
) -> pd.DataFrame:
    """Enumerate PV/storage candidates using existing energy-conserving dispatch.

    Feasible means zero unmet energy (1e-6 Wh tolerance) and, by default, final
    SOC >= initial SOC. The latter prevents initially charged batteries from
    disguising an energy deficit. This does not establish multi-year survival.
    Mass is an explicit panel+battery scenario excluding structures, conversion,
    insulation and redundancy. Battery properties are constant, not temperature
    or ageing dependent. Grid minimum is not a continuous global optimum.
    """
    areas, capacities = (
        np.asarray(array_areas_m2, dtype=float),
        np.asarray(capacities_wh, dtype=float),
    )
    for name, a in (("array_areas_m2", areas), ("capacities_wh", capacities)):
        if a.ndim != 1 or len(a) == 0 or not np.isfinite(a).all() or np.any(a <= 0):
            raise ValueError(f"{name} must be a nonempty positive vector")
    _positive(array_mass_kg_m2, "array_mass_kg_m2")
    _positive(battery_specific_energy_wh_kg, "battery_specific_energy_wh_kg")
    rows = []
    for area in areas:
        for capacity in capacities:
            battery = replace(battery_template, capacity_wh=float(capacity))
            dispatch = dispatch_power(
                time_s, np.asarray(generation_per_m2_w) * area, demand_w, battery=battery
            )
            unserved = float((dispatch.unserved_load_w * dispatch.duration_h).sum())
            terminal = float(dispatch.soc_end.iloc[-1])
            sustainable = terminal >= battery.initial_soc - 1e-10
            rows.append(
                dict(
                    array_area_m2=float(area),
                    capacity_wh=float(capacity),
                    unserved_energy_wh=unserved,
                    final_soc=terminal,
                    minimum_soc=float(dispatch.soc_end.min()),
                    terminal_soc_satisfied=sustainable,
                    feasible=unserved <= 1e-6 and (sustainable or not require_terminal_soc),
                    scenario_mass_kg=float(
                        area * array_mass_kg_m2 + capacity / battery_specific_energy_wh_kg
                    ),
                )
            )
    return pd.DataFrame(rows).sort_values("scenario_mass_kg").reset_index(drop=True)
