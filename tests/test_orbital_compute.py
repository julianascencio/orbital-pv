import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from orbitalpv.orbital_compute import (
    OrbitalComputeSpec,
    deployment_screen,
    screen_orbital_compute,
    simulate_orbital_compute,
)
from orbitalpv.physics import BatterySpec, dispatch_power

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "examples/space_business/_data/spacex_starmind.json").read_text())


@pytest.fixture
def base():
    values = dict(DATA["baseline"])
    battery = BatterySpec(**values.pop("battery"))
    return OrbitalComputeSpec(**values, battery=battery)


def test_no_eclipse_power_and_independent_radiator_balance(base):
    screen = screen_orbital_compute(base)
    # Independent AM0 input-to-bus chain; no STC/AM0 irradiance double count.
    expected = 1361 * 1000 * 0.25 * 0.9 * 0.875 * 0.95**2
    assert screen["sunlit_bus_power_kw"] == pytest.approx(expected / 1000)
    assert screen["sustainable_compute_kw"] == pytest.approx((expected - 15000) / 1000)
    assert screen["eclipse_min"] == 0
    assert screen["required_nominal_battery_kwh"] == 0
    flux = 0.9 * 5.670374419e-8 * (330**4 - 3**4) - 50
    assert screen["required_radiator_emitting_area_m2"] == pytest.approx(230000 / flux)


@pytest.mark.parametrize("scenario", DATA["scenarios"], ids=lambda s: s["name"])
def test_continuous_bound_is_repeatable_from_reserve(base, scenario):
    spec = replace(
        base,
        **scenario["changes"],
        battery=replace(base.battery, **scenario.get("battery_changes", {})),
    )
    screen = screen_orbital_compute(spec)
    period = float(screen["orbit_period_min"]) * 60
    eclipse = float(screen["eclipse_min"]) * 60
    sunlight = period - eclipse
    cycle_edges = [0, sunlight, period] if eclipse else [0, period]
    generation = (
        [float(screen["sunlit_bus_power_kw"]) * 1000, 0]
        if eclipse
        else [float(screen["sunlit_bus_power_kw"]) * 1000]
    )
    edges = np.r_[
        np.concatenate([np.array(cycle_edges[:-1]) + n * period for n in range(3)]), 3 * period
    ]
    trace = dispatch_power(
        edges,
        generation * 3,
        float(screen["sustainable_compute_kw"]) * 1000 + spec.platform_load_w,
        battery=replace(spec.battery, initial_soc=spec.battery.minimum_soc),
        maximum_served_power_w=float(screen["thermal_bus_limit_kw"]) * 1000,
    )
    assert trace.unserved_load_w.max() < 1e-7
    assert trace.soc_end.iloc[-1] >= spec.battery.minimum_soc - 1e-12


@pytest.mark.parametrize("scenario", DATA["scenarios"], ids=lambda s: s["name"])
def test_bursts_conserve_energy_and_repeat_without_free_initial_storage(base, scenario):
    spec = replace(
        base,
        **scenario["changes"],
        battery=replace(base.battery, **scenario.get("battery_changes", {})),
    )
    trace = simulate_orbital_compute(spec, cycles=40)
    assert trace.soc_start.iloc[0] == spec.battery.minimum_soc
    assert trace.power_balance_error_w.abs().max() < 1e-7
    # Integrated generation = load + curtailed energy + stored change + losses.
    residual = (
        (trace.generation_w - trace.served_load_w - trace.curtailed_w) * trace.duration_h
        - trace.stored_energy_change_wh
        - trace.battery_loss_wh
    )
    assert residual.abs().max() < 1e-7
    assert trace.soc_end.between(
        spec.battery.minimum_soc - 1e-12, spec.battery.maximum_soc + 1e-12
    ).all()
    assert not trace.thermal_allowance_exceeded.any()
    assert (
        trace.requested_compute_w * trace.duration_h
    ).sum() / trace.duration_h.sum() == pytest.approx(175000)
    last = trace[trace.cycle == 39]
    assert last.soc_end.iloc[-1] == pytest.approx(last.soc_start.iloc[0], abs=1e-10)
    if scenario["name"] in ("High-beta baseline", "Eclipse resized"):
        assert last.unserved_compute_wh.sum() < 1e-6
    else:
        assert last.unserved_compute_wh.sum() > 1000


def test_exact_shadow_and_burst_edges_remove_timestep_aliasing(base):
    spec = replace(base, beta_angle_deg=37)
    coarse = simulate_orbital_compute(spec, cycles=6, intervals_per_orbit=7)
    fine = simulate_orbital_compute(spec, cycles=6, intervals_per_orbit=240)
    for column in ("generation_w", "requested_load_w", "served_load_w"):
        assert (coarse[column] * coarse.duration_h).sum() == pytest.approx(
            (fine[column] * fine.duration_h).sum()
        )


def test_storage_cannot_fix_insufficient_orbit_energy(base):
    spec = replace(base, beta_angle_deg=0, battery=replace(base.battery, capacity_wh=1e8))
    screen = screen_orbital_compute(spec)
    assert not screen["average_target_feasible"]
    assert screen["required_pv_area_m2"] > spec.pv_area_m2


@pytest.mark.parametrize(
    "field,value",
    [
        ("pv_area_m2", -1),
        ("efficiency_am0", 1.1),
        ("beta_angle_deg", 91),
        ("retained_power_fraction", float("nan")),
        ("peak_compute_w", 100000),
        ("pv_temperature_c", -274),
        ("temperature_coefficient_per_k", -1),
    ],
)
def test_invalid_design_inputs(base, field, value):
    with pytest.raises(ValueError):
        replace(base, **{field: value})


def test_unbudgeted_eps_heat_is_rejected(base):
    with pytest.raises(ValueError, match="loss bound"):
        screen_orbital_compute(replace(base, thermal_allowance_w=0))


def test_deployment_keeps_stc_factory_array_and_compute_watts_separate():
    result = deployment_screen(**DATA["deployment"], array_area_m2=1000, continuous_compute_kw=175)
    assert result["array_stc_kw"] == 225
    assert result["arrays_per_year"] == 160000
    assert result["deployed_satellites_per_year"] == 20000
    assert result["launches_to_deploy_factory_output"] == 8000
    assert result["deployed_array_stc_gw_per_year"] == 4.5
    assert result["added_continuous_compute_gw"] == 3.5
    assert result["added_utilized_compute_gw"] == pytest.approx(2.975)


def test_zero_launches_and_unlaunchable_spacecraft():
    args = dict(DATA["deployment"], array_area_m2=1000, continuous_compute_kw=175)
    assert deployment_screen(**{**args, "launches_per_year": 0})["added_continuous_compute_gw"] == 0
    result = deployment_screen(**{**args, "satellite_mass_kg": 100001})
    assert result["deployed_satellites_per_year"] == 0
    assert result["launches_to_deploy_factory_output"] is None


@pytest.mark.parametrize("invalid_launches", [1.5, -1, float("nan"), True])
def test_invalid_launch_cadence(invalid_launches):
    args = dict(DATA["deployment"], array_area_m2=1000, continuous_compute_kw=175)
    with pytest.raises(ValueError):
        deployment_screen(**{**args, "launches_per_year": invalid_launches})


@pytest.mark.parametrize("scenario", DATA["scenarios"], ids=lambda s: s["name"])
def test_continuous_cap_protects_platform_and_accounts_rejection(base, scenario):
    spec = replace(
        base,
        **scenario["changes"],
        battery=replace(base.battery, **scenario.get("battery_changes", {})),
    )
    trace = simulate_orbital_compute(spec, cycles=4, dispatch_policy="continuous_cap")
    assert (spec.platform_load_w - trace.served_platform_w).max() < 1e-7
    assert trace.power_balance_error_w.abs().max() < 1e-6
    assert trace.unserved_load_w.max() < 1e-7
    assert trace.soc_end.iloc[-1] >= spec.battery.minimum_soc - 1e-10
    np.testing.assert_allclose(trace.unserved_compute_wh, trace.rejected_compute_wh, atol=1e-6)
    assert (trace.admitted_compute_w <= trace.requested_compute_w).all()


def test_policy_validation_and_impossible_platform(base):
    with pytest.raises(ValueError, match="dispatch_policy"):
        simulate_orbital_compute(base, dispatch_policy="unknown")
    with pytest.raises(ValueError, match="feasible platform"):
        simulate_orbital_compute(
            replace(base, platform_load_w=300000), dispatch_policy="continuous_cap"
        )


def test_cap_removes_greedy_platform_outage(base):
    spec = replace(base, beta_angle_deg=0)
    greedy = simulate_orbital_compute(spec, cycles=4)
    capped = simulate_orbital_compute(spec, cycles=4, dispatch_policy="continuous_cap")
    assert (spec.platform_load_w - greedy.served_platform_w).max() > 1000
    assert (spec.platform_load_w - capped.served_platform_w).max() < 1e-7
    assert (capped.rejected_compute_wh > 0).any()
