"""Verify inverse reserve using analytical cases and independent forward dispatch."""

from dataclasses import replace

import numpy as np
import pytest

from orbitalpv.physics import (
    BatterySpec,
    InfeasibleReserveError,
    battery_reserve_envelope,
    dispatch_power,
)


def test_known_deficit_and_efficiency():
    battery = BatterySpec(1000, discharge_efficiency=0.8)
    result = battery_reserve_envelope([0, 3600], 20, 100, battery=battery, terminal_soc=0.3)
    np.testing.assert_allclose(result.required_energy_wh, [400, 300])


def test_surplus_clipped_by_charger_and_minimum():
    battery = BatterySpec(1000, charge_efficiency=0.8, max_charge_w=100)
    result = battery_reserve_envelope([0, 3600, 7200], 1000, 0, battery=battery, terminal_soc=0.2)
    np.testing.assert_allclose(result.required_energy_wh, [100, 120, 200])


def test_energy_timing_cannot_be_replaced_by_net_energy():
    battery = BatterySpec(
        100, maximum_soc=1, initial_soc=1, charge_efficiency=1, discharge_efficiency=1
    )
    with pytest.raises(InfeasibleReserveError, match="capacity"):
        battery_reserve_envelope(
            [0, 3600, 7200], [100, 0], [0, 100], battery=battery, terminal_soc=0.1
        )


def test_converter_limit_despite_adequate_energy():
    with pytest.raises(InfeasibleReserveError, match="power limit"):
        battery_reserve_envelope(
            [0, 1], 0, 101, battery=BatterySpec(10000, max_discharge_w=100), terminal_soc=0.2
        )


def test_initial_soc_is_not_an_input_to_required_envelope():
    low = BatterySpec(1000, initial_soc=0.1)
    a = battery_reserve_envelope([0, 3600], 0, 100, battery=low, terminal_soc=0.3)
    b = battery_reserve_envelope(
        [0, 3600], 0, 100, battery=replace(low, initial_soc=0.9), terminal_soc=0.3
    )
    np.testing.assert_array_equal(a.required_soc, b.required_soc)


def test_split_intervals_preserve_requirement():
    battery = BatterySpec(1000)
    a = battery_reserve_envelope([0, 3600], 100, 200, battery=battery, terminal_soc=0.4)
    b = battery_reserve_envelope([0, 300, 2100, 3600], 100, 200, battery=battery, terminal_soc=0.4)
    assert a.required_soc.iloc[0] == pytest.approx(b.required_soc.iloc[0])


def test_boundary_feasibility_and_minimality_across_random_profiles():
    rng = np.random.default_rng(20261121)
    checked = 0
    for _ in range(100):
        times = np.r_[0, np.cumsum(rng.uniform(100, 2000, 8))]
        generation = rng.uniform(0, 600, 8)
        load = rng.uniform(50, 300, 8)
        battery = BatterySpec(1000, max_charge_w=200, max_discharge_w=300)
        try:
            envelope = battery_reserve_envelope(
                times, generation, load, battery=battery, terminal_soc=0.5
            )
        except InfeasibleReserveError:
            full = dispatch_power(
                times, generation, load, battery=replace(battery, initial_soc=battery.maximum_soc)
            )
            assert (full.unserved_load_w > 1e-7).any() or full.soc_end.iloc[-1] < 0.5 - 1e-9
            continue
        required = float(envelope.required_soc.iloc[0])
        forward = dispatch_power(
            times, generation, load, battery=replace(battery, initial_soc=required)
        )
        assert forward.unserved_load_w.max() < 1e-7
        assert forward.soc_end.iloc[-1] >= 0.5 - 1e-9
        if required > battery.minimum_soc + 1e-4:
            below = dispatch_power(
                times, generation, load, battery=replace(battery, initial_soc=required - 1e-4)
            )
            assert below.unserved_load_w.max() > 1e-7 or below.soc_end.iloc[-1] < 0.5 - 1e-9
        checked += 1
    assert checked > 20


@pytest.mark.parametrize("terminal", [float("nan"), float("inf"), 0.05, 1.01])
def test_terminal_bounds(terminal):
    with pytest.raises(ValueError, match="terminal_soc"):
        battery_reserve_envelope([0, 3600], 0, 0, battery=BatterySpec(1000), terminal_soc=terminal)


@pytest.mark.parametrize(
    "times,generation,demand",
    [([0, 0], 0, 0), ([0, 1], -1, 0), ([0, 1], 0, float("nan")), ([0, 1, 2], [1, 2, 3], 0)],
)
def test_invalid_profile(times, generation, demand):
    with pytest.raises(ValueError):
        battery_reserve_envelope(
            times, generation, demand, battery=BatterySpec(1000), terminal_soc=0.5
        )
