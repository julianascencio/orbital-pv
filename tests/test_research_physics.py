"""Independent physical invariants and failure paths for research models."""

from dataclasses import replace

import numpy as np
import pytest

from orbitalpv import physics as physics


def test_adiabatic_thermal_energy_conservation() -> None:
    surface = physics.ThermalSurface(
        area_m2=1, heat_capacity_j_k=100, solar_absorptivity=1, ir_emissivity=0
    )
    trace = physics.simulate_panel_thermal(
        [0, 10, 20],
        20,
        surface=surface,
        pv_efficiency=0,
        initial_temperature_k=300,
        max_step_s=100,
    )
    np.testing.assert_allclose(trace.temperature_k, [300, 302, 304])
    np.testing.assert_allclose(trace.energy_balance_error_j, 0, atol=1e-8)


def test_implicit_thermal_step_is_positive_and_cools() -> None:
    surface = physics.ThermalSurface(heat_capacity_j_k=1, sink_temperature_k=0)
    trace = physics.simulate_panel_thermal(
        [0, 3600],
        0,
        surface=surface,
        pv_efficiency=0,
        initial_temperature_k=400,
        max_step_s=3600,
    )
    assert 0 < trace.temperature_k.iloc[-1] < 400
    np.testing.assert_allclose(trace.energy_balance_error_j, 0, atol=1e-7)


def test_thermal_dark_cooling_converges_to_analytic_solution() -> None:
    surface = physics.ThermalSurface(heat_capacity_j_k=10_000, sink_temperature_k=0)
    time = np.linspace(0, 600, 61)
    coefficient = surface.ir_emissivity * 5.670374419e-8 * surface.radiating_area_m2
    exact = (300.0**-3 + 3 * coefficient * time / surface.heat_capacity_j_k) ** (-1 / 3)
    trace = physics.simulate_panel_thermal(
        time, 0, surface=surface, initial_temperature_k=300, pv_efficiency=0, max_step_s=1
    )
    np.testing.assert_allclose(trace.temperature_k, exact, atol=0.02)


def test_electrical_extraction_cools_surface_and_ir_does_not_generate_power() -> None:
    time = np.arange(0, 3601, 60)
    zero = physics.simulate_panel_thermal(time, 1000, pv_efficiency=0)
    pv = physics.simulate_panel_thermal(time, 1000, pv_efficiency=0.25)
    ir_only = physics.simulate_panel_thermal(time, 0, earth_ir_w_m2=250)
    assert pv.temperature_k.iloc[-1] < zero.temperature_k.iloc[-1]
    assert np.all(ir_only.pv_power_w == 0)
    np.testing.assert_allclose(pv.energy_balance_error_j, 0, atol=1e-6)


def test_radiation_niel_integral_and_shielding_limits() -> None:
    exposure = physics.radiation_equivalent_fluence([1, 2, 3], 10, 2, reference_niel_mev_cm2_g=4)
    assert exposure.transmitted_fluence_cm2 == pytest.approx(20)
    assert exposure.displacement_damage_mev_g == pytest.approx(40)
    assert exposure.equivalent_fluence_cm2 == pytest.approx(10)
    blocked = physics.radiation_equivalent_fluence(
        [1, 2, 3], 10, 2, reference_niel_mev_cm2_g=4, shielding_transmission=0
    )
    assert blocked.equivalent_fluence_cm2 == 0
    with pytest.raises(ValueError, match="transmission"):
        physics.radiation_equivalent_fluence(
            [1, 2], 10, 2, reference_niel_mev_cm2_g=4, shielding_transmission=2
        )


def test_retention_bounds_monotonicity_and_zero_exposure() -> None:
    response = physics.RadiationResponse(0.3, 1e12, minimum_retention=0.1)
    retention = physics.retained_power_fraction([0, 1e12, 1e14, 1e20], response)
    assert retention[0] == 1
    assert np.all(np.diff(retention) <= 0)
    assert np.all((retention >= 0.1) & (retention <= 1))


def test_spectral_current_matches_analytic_flat_spectrum() -> None:
    wavelength = np.linspace(400, 800, 101)
    expected = 1.602176634e-19 / (6.62607015e-34 * 299792458) * 1e-9 * (800**2 - 400**2) / 2
    current = physics.spectral_photocurrent_density(wavelength, np.ones(101), np.ones(101))
    assert float(current) == pytest.approx(expected)
    assert (
        float(physics.spectral_photocurrent_density(wavelength, np.zeros(101), np.ones(101))) == 0
    )


def test_tandem_current_is_limited_and_no_photon_double_counting() -> None:
    wavelength = np.linspace(400, 800, 101)
    result = physics.tandem_current_density(
        wavelength, np.ones(101), np.tile([0.2, 0.4], (101, 1)).T
    )
    assert result.series_current_a_m2 == pytest.approx(result.subcell_current_a_m2[0])
    assert result.current_mismatch_fraction == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="photon"):
        physics.tandem_current_density(wavelength, np.ones(101), np.ones((2, 101)))


def test_array_series_parallel_scaling_and_power_identity() -> None:
    component = physics.PVSubstring(5, 20, diode_voltage_v=0.8)
    voltage = np.linspace(0, 20, 501)
    single = physics.array_iv_curve([[component]], voltage)
    series = physics.array_iv_curve([[component, component]], 2 * voltage)
    parallel = physics.array_iv_curve([[component], [component]], voltage)
    np.testing.assert_allclose(series.current_a, single.current_a)
    np.testing.assert_allclose(parallel.current_a, 2 * single.current_a)
    np.testing.assert_allclose(series.power_w, 2 * single.power_w)
    assert np.all(np.diff(single.current_a) <= 1e-10)
    assert single.current_a.iloc[-1] == 0
    assert np.all(single.power_w >= 0)


def test_bypass_prevents_shaded_substring_from_limiting_entire_string() -> None:
    healthy = physics.PVSubstring(5, 20)
    shade = physics.PVSubstring(0.5, 18)
    voltage = np.linspace(0, 60, 601)
    bypassed = physics.array_iv_curve([[healthy, healthy, shade]], voltage)
    unbypassed = physics.array_iv_curve(
        [[healthy, healthy, replace(shade, bypass_voltage_v=None)]], voltage
    )
    assert bypassed.attrs["pmp_w"] > unbypassed.attrs["pmp_w"]
    broken = physics.array_iv_curve(
        [[healthy, replace(shade, fault="open", bypass_voltage_v=None)]]
    )
    assert np.all(broken.current_a == 0)


def test_battery_dispatch_conserves_energy_and_obeys_limits() -> None:
    battery = physics.BatterySpec(
        10,
        initial_soc=0.5,
        minimum_soc=0.2,
        maximum_soc=0.8,
        charge_efficiency=0.8,
        discharge_efficiency=0.9,
    )
    trace = physics.dispatch_power(
        [0, 3600, 7200, 10800], [100, 0, 0], [0, 100, 1], battery=battery
    )
    assert trace.soc_end.iloc[0] == pytest.approx(0.8)
    assert trace.soc_end.iloc[1] == pytest.approx(0.2)
    assert trace.unserved_load_w.iloc[1] > 0
    assert trace.curtailed_w.iloc[0] > 0
    np.testing.assert_allclose(trace.power_balance_error_w, 0, atol=1e-12)
    np.testing.assert_allclose(
        trace.stored_energy_change_wh, (trace.soc_end - trace.soc_start) * 10
    )
    assert np.all(trace.charge_w * trace.discharge_w == 0)


def test_rainflow_closed_and_residual_cycles() -> None:
    cycles = physics.rainflow_cycles([0, 1, 0])
    assert float(cycles["count"].sum()) == pytest.approx(1)
    assert np.all(cycles.depth_of_discharge == 1)
    assert physics.battery_cycle_damage(
        [0, 1, 0], cycles_to_failure_at_full_depth=1000
    ) == pytest.approx(0.001)
    assert physics.rainflow_cycles([0.5, 0.5, 0.5]).empty
    residual = physics.rainflow_cycles([0.2, 0.8])
    assert residual["count"].iloc[0] == 0.5


def test_compute_tasks_respect_deadline_thermal_limit_and_energy_accounting() -> None:
    battery = physics.BatterySpec(20, initial_soc=0.9)
    task = physics.ComputeTask(4, 0, 7200, 10)
    trace, tasks = physics.schedule_compute_workload(
        [0, 3600, 7200],
        [20, 0],
        [2, 2],
        battery=battery,
        tasks=[task],
        compute_power_limit_w=10,
        thermal_power_limit_w=5,
    )
    assert np.all(trace.served_load_w <= 5)
    assert tasks.completed_energy_wh.iloc[0] == pytest.approx(4)
    assert tasks.unserved_energy_wh.iloc[0] == pytest.approx(0)
    assert float((trace.served_compute_w * trace.duration_h).sum()) == pytest.approx(4)
    np.testing.assert_allclose(trace.power_balance_error_w, 0, atol=1e-10)


def test_missed_deadline_is_reported_and_no_late_execution() -> None:
    task = physics.ComputeTask(10, 0, 3600, 10)
    trace, tasks = physics.schedule_compute_workload(
        [0, 3600, 7200],
        [0, 100],
        0,
        battery=physics.BatterySpec(10, initial_soc=0.1, minimum_soc=0.1),
        tasks=[task],
        compute_power_limit_w=10,
    )
    assert tasks.unserved_energy_wh.iloc[0] == 10
    assert np.all(trace.served_compute_w == 0)


@pytest.mark.parametrize(("compute_limit", "thermal_limit"), [(2.0, None), (10.0, 2.0)])
def test_deadline_lookahead_respects_system_power_bottlenecks(
    compute_limit: float, thermal_limit: float | None
) -> None:
    """A feasible single task must start now when its actual cap is only 2 W."""
    trace, tasks = physics.schedule_compute_workload(
        [0, 3600, 7200],
        0,
        0,
        battery=physics.BatterySpec(100, initial_soc=0.9),
        tasks=[physics.ComputeTask(4, 0, 7200, 10)],
        compute_power_limit_w=compute_limit,
        thermal_power_limit_w=thermal_limit,
    )
    np.testing.assert_allclose(trace.served_compute_w, [2, 2])
    assert tasks.completed_energy_wh.iloc[0] == pytest.approx(4)
    assert tasks.unserved_energy_wh.iloc[0] == pytest.approx(0)
    np.testing.assert_allclose(trace.power_balance_error_w, 0, atol=1e-12)


def test_deadline_lookahead_integrates_future_thermal_availability() -> None:
    """The task must use the middle hour: later thermal capacity is zero."""
    trace, tasks = physics.schedule_compute_workload(
        [0, 3600, 7200, 10800],
        0,
        0,
        battery=physics.BatterySpec(100, initial_soc=0.9),
        tasks=[physics.ComputeTask(2, 0, 10800, 10)],
        compute_power_limit_w=10,
        thermal_power_limit_w=[0, 2, 0],
    )
    np.testing.assert_allclose(trace.served_compute_w, [0, 2, 0])
    assert tasks.unserved_energy_wh.iloc[0] == pytest.approx(0)


def test_radiator_area_scaling_and_impossible_environment() -> None:
    result = physics.radiator_feasibility(100, area_m2=1, radiator_temperature_k=300)
    twice = physics.radiator_feasibility(100, area_m2=2, radiator_temperature_k=300)
    assert twice["available_heat_rejection_w"] == pytest.approx(
        2 * result["available_heat_rejection_w"]
    )
    impossible = physics.radiator_feasibility(
        100, area_m2=1, radiator_temperature_k=300, absorbed_environment_w_m2=1000
    )
    assert not impossible["feasible"]
    assert np.isinf(impossible["required_area_m2"])


@pytest.mark.parametrize("times", [[0, 0], [1, 0], [0, np.nan]])
def test_invalid_time_grids_rejected(times: list[float]) -> None:
    with pytest.raises(ValueError):
        physics.simulate_panel_thermal(times, 1000)
    with pytest.raises(ValueError):
        physics.dispatch_power(times, 1, 1, battery=physics.BatterySpec(1))
