"""Screen solar-powered orbital compute against power, heat and launch limits.

This composes OrbitalPV's circular-shadow, periodic-load and battery-dispatch
models. Inputs are design assumptions, not a flight-qualified spacecraft model.
The radiator has a prescribed temperature and total emitting area, not a CAD
footprint. A fixed heat allowance reserves capacity for EPS/storage losses.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil, floor

import numpy as np
import pandas as pd

from .orbit import circular_eclipse_duration_s, circular_orbit_period_s
from .physics import BatterySpec, dispatch_power, periodic_load_limit, radiator_feasibility


def _positive(name: str, value: float, *, zero: bool = False) -> None:
    if not np.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")


@dataclass(frozen=True)
class OrbitalComputeSpec:
    """Explicit SI inputs; AM0 efficiency must be independently characterized.

    ``pv_area_m2`` is the deployed array footprint. Packing excludes inactive
    area; derate covers mismatch/wiring, and EPS efficiency is separate.
    Retention is an imposed sensitivity, not a prediction of radiation damage.
    ``thermal_allowance_w`` must cover converter/storage heat on this radiator;
    PV blanket absorption is assumed to radiate through its separate surface.
    """

    altitude_m: float
    beta_angle_deg: float
    pv_area_m2: float
    efficiency_am0: float
    packing_fraction: float
    pv_temperature_c: float
    temperature_coefficient_per_k: float
    array_derate: float
    eps_efficiency: float
    retained_power_fraction: float
    irradiance_w_m2: float
    platform_load_w: float
    average_compute_w: float
    peak_compute_w: float
    radiator_emitting_area_m2: float
    radiator_temperature_k: float
    radiator_emissivity: float
    absorbed_environment_w_m2: float
    thermal_allowance_w: float
    battery: BatterySpec

    def __post_init__(self) -> None:
        for name in (
            "altitude_m",
            "pv_area_m2",
            "irradiance_w_m2",
            "average_compute_w",
            "peak_compute_w",
            "radiator_emitting_area_m2",
            "radiator_temperature_k",
        ):
            _positive(name, getattr(self, name))
        for name in ("platform_load_w", "absorbed_environment_w_m2", "thermal_allowance_w"):
            _positive(name, getattr(self, name), zero=True)
        for name in (
            "efficiency_am0",
            "packing_fraction",
            "array_derate",
            "eps_efficiency",
            "retained_power_fraction",
            "radiator_emissivity",
        ):
            value = getattr(self, name)
            if not np.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f"{name} must lie in (0, 1]")
        if not np.isfinite(self.beta_angle_deg) or abs(self.beta_angle_deg) > 90:
            raise ValueError("beta_angle_deg must lie in [-90, 90]")
        if not np.isfinite(self.pv_temperature_c) or self.pv_temperature_c <= -273.15:
            raise ValueError("pv_temperature_c must be finite and above absolute zero")
        if not np.isfinite(self.temperature_coefficient_per_k):
            raise ValueError("temperature_coefficient_per_k must be finite")
        factor = 1 + self.temperature_coefficient_per_k * (self.pv_temperature_c - 25)
        if factor <= 0 or self.efficiency_am0 * factor > 1:
            raise ValueError("temperature correction gives a nonphysical PV efficiency")
        if self.peak_compute_w < self.average_compute_w:
            raise ValueError("peak_compute_w must be at least average_compute_w")


def screen_orbital_compute(spec: OrbitalComputeSpec) -> dict[str, float | bool]:
    """Calculate repeatable continuous compute and necessary sizing conditions.

    The electrical bound includes orbit energy, SOC window and battery power
    limits. Heat rejection assumes all served electrical load becomes heat.
    Neither a nameplate compute rating nor an initially full battery creates
    sustainable energy. Area/storage requirements alone are not sufficient:
    charge/discharge ratings and thermal capacity must also pass.
    """
    period_h = circular_orbit_period_s(spec.altitude_m) / 3600
    eclipse_h = float(circular_eclipse_duration_s(spec.altitude_m, spec.beta_angle_deg)) / 3600
    sunlight_h = period_h - eclipse_h
    temperature_factor = 1 + spec.temperature_coefficient_per_k * (spec.pv_temperature_c - 25)
    bus_density = (
        spec.irradiance_w_m2
        * spec.efficiency_am0
        * spec.packing_fraction
        * temperature_factor
        * spec.array_derate
        * spec.eps_efficiency
        * spec.retained_power_fraction
    )
    sunlit_power = bus_density * spec.pv_area_m2
    # Conservative bound: EPS loss plus the larger battery conversion loss.
    # Charge/discharge do not occur simultaneously. Counting EPS loss during
    # discharge as well is conservative; curtailed generation is included.
    loss_bound = sunlit_power * (1 / spec.eps_efficiency - 1) + max(
        min(sunlit_power, spec.battery.max_charge_w) * (1 - spec.battery.charge_efficiency),
        min(spec.peak_compute_w + spec.platform_load_w, spec.battery.max_discharge_w)
        * (1 / spec.battery.discharge_efficiency - 1),
    )
    if spec.thermal_allowance_w + 1e-8 < loss_bound:
        raise ValueError("thermal_allowance_w must cover the conservative EPS/battery loss bound")
    limits = periodic_load_limit(sunlit_power, sunlight_h, eclipse_h, battery=spec.battery)
    target = spec.platform_load_w + spec.average_compute_w
    radiator = radiator_feasibility(
        target + spec.thermal_allowance_w,
        area_m2=spec.radiator_emitting_area_m2,
        radiator_temperature_k=spec.radiator_temperature_k,
        emissivity=spec.radiator_emissivity,
        absorbed_environment_w_m2=spec.absorbed_environment_w_m2,
    )
    thermal_bus_limit = max(
        float(radiator["available_heat_rejection_w"]) - spec.thermal_allowance_w, 0
    )
    total_limit = min(limits["sustainable_load_w"], thermal_bus_limit)
    compute_limit = min(spec.peak_compute_w, max(total_limit - spec.platform_load_w, 0))
    battery = spec.battery
    roundtrip = battery.charge_efficiency * battery.discharge_efficiency
    required_sunlit = target * (1 + eclipse_h / (sunlight_h * roundtrip))
    soc_window = battery.maximum_soc - battery.minimum_soc
    required_battery = (
        target * eclipse_h / (soc_window * battery.discharge_efficiency)
        if eclipse_h > 0 and soc_window > 0
        else (float("inf") if eclipse_h > 0 else 0.0)
    )
    required_charge = target * eclipse_h / (sunlight_h * roundtrip)
    return {
        "orbit_period_min": period_h * 60,
        "eclipse_min": eclipse_h * 60,
        "sunlight_fraction": sunlight_h / period_h,
        "sunlit_bus_power_kw": sunlit_power / 1000,
        "eps_battery_heat_bound_kw": loss_bound / 1000,
        "electrical_bus_limit_kw": limits["sustainable_load_w"] / 1000,
        "thermal_bus_limit_kw": thermal_bus_limit / 1000,
        "sustainable_compute_kw": compute_limit / 1000,
        "average_target_feasible": bool(compute_limit >= spec.average_compute_w - 1e-8),
        "platform_continuous_feasible": bool(total_limit >= spec.platform_load_w),
        "required_pv_area_m2": required_sunlit / bus_density,
        "required_nominal_battery_kwh": required_battery / 1000,
        "required_charge_kw": required_charge / 1000,
        "required_discharge_kw": target / 1000 if eclipse_h > 0 else 0.0,
        "required_radiator_emitting_area_m2": float(radiator["required_area_m2"]),
    }


def simulate_orbital_compute(
    spec: OrbitalComputeSpec,
    *,
    cycles: int = 40,
    intervals_per_orbit: int = 120,
    peak_fraction: float = 0.2,
) -> pd.DataFrame:
    """Dispatch orbit-repeating bursts with exactly the requested mean load.

    Each cycle starts in sunlight, followed by eclipse. The peak occupies the
    last ``peak_fraction`` of each orbit (a deliberately adverse alignment).
    Boundaries include shadow entry and burst start exactly, avoiding timestep
    aliasing. Platform demand has priority within each interval, with no
    lookahead reserve for future platform demand; overload can cause outages.
    A fixed radiator cap excludes
    thermal inertia, and the full trace reports SOC drift and unserved energy.
    Initial SOC is set to the reserve floor to avoid gifting stored energy.
    """
    if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 1:
        raise ValueError("cycles must be a positive integer")
    if (
        isinstance(intervals_per_orbit, bool)
        or not isinstance(intervals_per_orbit, int)
        or intervals_per_orbit < 2
    ):
        raise ValueError("intervals_per_orbit must be an integer >= 2")
    if not np.isfinite(peak_fraction) or not 0 <= peak_fraction < 1:
        raise ValueError("peak_fraction must lie in [0, 1)")
    low_compute = (spec.average_compute_w - peak_fraction * spec.peak_compute_w) / (
        1 - peak_fraction
    )
    if low_compute < 0:
        raise ValueError("peak_fraction makes the off-peak compute load negative")
    screen = screen_orbital_compute(spec)
    period = float(screen["orbit_period_min"]) * 60
    eclipse = float(screen["eclipse_min"]) * 60
    sun_end = period - eclipse
    peak_start = period * (1 - peak_fraction)
    one_cycle = np.unique(
        np.r_[np.linspace(0, period, intervals_per_orbit + 1), sun_end, peak_start]
    )
    # Merge a transition that coincides with a regular edge to floating-point
    # precision before shifting many cycles (otherwise tiny gaps can collapse).
    one_cycle = one_cycle[np.r_[True, np.diff(one_cycle) > period * 1e-12]]
    edges = np.r_[
        np.concatenate([one_cycle[:-1] + i * period for i in range(cycles)]), cycles * period
    ]
    phase = ((edges[:-1] + edges[1:]) / 2) % period
    generation = np.where(phase < sun_end, float(screen["sunlit_bus_power_kw"]) * 1000, 0)
    compute = np.where(phase >= peak_start, spec.peak_compute_w, low_compute)
    trace = dispatch_power(
        edges,
        generation,
        compute + spec.platform_load_w,
        battery=replace(spec.battery, initial_soc=spec.battery.minimum_soc),
        maximum_served_power_w=float(screen["thermal_bus_limit_kw"]) * 1000,
    )
    trace["cycle"] = np.floor(((edges[:-1] + edges[1:]) / 2) / period).astype(int)
    trace["requested_compute_w"] = compute
    trace["served_platform_w"] = np.minimum(trace.served_load_w, spec.platform_load_w)
    trace["served_compute_w"] = trace.served_load_w - trace.served_platform_w
    trace["unserved_compute_wh"] = (compute - trace.served_compute_w) * trace.duration_h
    # Conservative check: even curtailed array output is charged to EPS losses.
    trace["modeled_eps_battery_heat_w"] = (
        generation * (1 / spec.eps_efficiency - 1) + trace.battery_loss_wh / trace.duration_h
    )
    trace["thermal_allowance_exceeded"] = (
        trace.modeled_eps_battery_heat_w > spec.thermal_allowance_w + 1e-8
    )
    return trace


def deployment_screen(
    *,
    manufacturing_gw_per_year: float,
    factory_utilization: float,
    manufacturing_yield: float,
    space_allocation_fraction: float,
    array_area_m2: float,
    packing_fraction: float,
    efficiency_stc: float,
    satellite_mass_kg: float,
    payload_to_target_orbit_kg: float,
    launches_per_year: int,
    continuous_compute_kw: float,
    compute_utilization: float = 1.0,
) -> dict[str, float | int | None]:
    """Annual deployment ceiling on an explicitly assumed STC factory basis.

    Annual GW nameplate production is NOT delivered orbital GW or compute GW.
    Array watts here use 1000 W/m² STC and a separately supplied efficiency.
    Full spacecraft mass includes PV, radiator, storage and structure. Launch
    throughput is mass-only: fairing volume, deployment reliability, networking,
    approvals, satellite factory throughput and replacements are excluded.
    """
    for name, value in (
        ("manufacturing_gw_per_year", manufacturing_gw_per_year),
        ("continuous_compute_kw", continuous_compute_kw),
    ):
        _positive(name, value, zero=True)
    for name, value in (
        ("array_area_m2", array_area_m2),
        ("satellite_mass_kg", satellite_mass_kg),
        ("payload_to_target_orbit_kg", payload_to_target_orbit_kg),
    ):
        _positive(name, value)
    for name, value in (
        ("factory_utilization", factory_utilization),
        ("manufacturing_yield", manufacturing_yield),
        ("space_allocation_fraction", space_allocation_fraction),
        ("compute_utilization", compute_utilization),
    ):
        if not np.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must lie in [0, 1]")
    for name, value in (("packing_fraction", packing_fraction), ("efficiency_stc", efficiency_stc)):
        if not np.isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"{name} must lie in (0, 1]")
    if (
        isinstance(launches_per_year, bool)
        or not isinstance(launches_per_year, int)
        or launches_per_year < 0
    ):
        raise ValueError("launches_per_year must be a nonnegative integer")
    array_stc_kw = array_area_m2 * packing_fraction * efficiency_stc
    usable_gw = (
        manufacturing_gw_per_year
        * factory_utilization
        * manufacturing_yield
        * space_allocation_fraction
    )
    arrays = floor(usable_gw * 1e6 / array_stc_kw)
    per_launch = floor(payload_to_target_orbit_kg / satellite_mass_kg)
    launched = min(arrays, per_launch * launches_per_year)
    return {
        "array_stc_kw": array_stc_kw,
        "usable_factory_gw_per_year": usable_gw,
        "arrays_per_year": arrays,
        "satellites_per_launch": per_launch,
        "launch_limited_satellites_per_year": per_launch * launches_per_year,
        "deployed_satellites_per_year": launched,
        "launches_to_deploy_factory_output": ceil(arrays / per_launch)
        if per_launch
        else (0 if arrays == 0 else None),
        "launch_payload_can_fit_one_satellite": int(per_launch > 0),
        "deployed_array_stc_gw_per_year": launched * array_stc_kw / 1e6,
        "added_continuous_compute_gw": launched * continuous_compute_kw / 1e6,
        "added_utilized_compute_gw": launched * continuous_compute_kw * compute_utilization / 1e6,
    }
