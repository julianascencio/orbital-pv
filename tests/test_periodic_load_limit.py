from dataclasses import replace

import pytest

from orbitalpv.physics import BatterySpec, dispatch_power, periodic_load_limit


@pytest.mark.parametrize(
    "capacity,charge,discharge",
    [
        (80000, 200000, 200000),
        (120000, 200000, 200000),
        (120000, 10000, 200000),
        (120000, 200000, 20000),
    ],
)
def test_bound_is_feasible_and_tight(capacity, charge, discharge):
    battery = BatterySpec(
        capacity_wh=capacity,
        initial_soc=0.2,
        minimum_soc=0.2,
        maximum_soc=0.9,
        max_charge_w=charge,
        max_discharge_w=discharge,
    )
    bound = periodic_load_limit(215000, 1, 35 / 60, battery=battery)["sustainable_load_w"]
    for factor in (1, 1.01):
        trace = dispatch_power([0, 3600, 5700], [215000, 0], bound * factor, battery=battery)
        assert (trace.unserved_load_w.max() < 1e-7) == (factor == 1)
        assert trace.power_balance_error_w.abs().max() < 1e-7


def test_lossless_energy_and_no_eclipse():
    battery = BatterySpec(capacity_wh=1e6, charge_efficiency=1, discharge_efficiency=1)
    assert periodic_load_limit(100, 1, 1, battery=battery)["sustainable_load_w"] == 50
    assert (
        periodic_load_limit(100, 1, 0, battery=replace(battery, max_discharge_w=0))[
            "sustainable_load_w"
        ]
        == 100
    )
    assert periodic_load_limit(0, 1, 1, battery=battery)["sustainable_load_w"] == 0


@pytest.mark.parametrize(
    "pv,sun,eclipse",
    [(-1, 1, 1), (1, 0, 1), (1, 1, -1), (float("nan"), 1, 1), (1, 1, float("inf"))],
)
def test_invalid_inputs(pv, sun, eclipse):
    with pytest.raises(ValueError):
        periodic_load_limit(pv, sun, eclipse, battery=BatterySpec(100))
