import math

import pytest

from orbitalpv.physics import dc_cable_delivery

BASE = dict(
    source_voltage_v=100,
    load_w=800,
    length_m=1,
    conductor_area_mm2=1,
    resistivity_ohm_m=1e-6,
    density_kg_m3=1000,
)


def test_independent_quadratic_and_energy_balance():
    r = dc_cable_delivery(**BASE)
    assert r["loop_resistance_ohm"] == pytest.approx(2)
    assert r["receiving_voltage_v"] == pytest.approx(80)
    assert r["current_a"] == pytest.approx(10)
    assert r["cable_loss_w"] == pytest.approx(200)
    assert r["source_power_w"] == pytest.approx(1000)
    assert r["conductor_mass_kg"] == pytest.approx(0.002)
    assert not r["voltage_criterion_pass"]


@pytest.mark.parametrize("power,exists", [(1250, True), (1251, False)])
def test_transfer_limit(power, exists):
    r = dc_cable_delivery(**{**BASE, "load_w": power})
    assert r["equilibrium_exists"] == exists
    assert not r["voltage_criterion_pass"]
    if not exists:
        assert math.isnan(r["cable_loss_w"])


def test_higher_voltage_and_area_reduce_loss():
    original = dc_cable_delivery(**BASE)
    voltage = dc_cable_delivery(**{**BASE, "source_voltage_v": 200})
    area = dc_cable_delivery(**{**BASE, "conductor_area_mm2": 2})
    assert voltage["cable_loss_w"] < original["cable_loss_w"]
    assert area["cable_loss_w"] < original["cable_loss_w"]
    assert area["conductor_mass_kg"] == 2 * original["conductor_mass_kg"]


@pytest.mark.parametrize("key", list(BASE))
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_inputs(key, value):
    with pytest.raises(ValueError):
        dc_cable_delivery(**{**BASE, key: value})


@pytest.mark.parametrize("fraction", [0.5, 1.1])
def test_voltage_constraint(fraction):
    with pytest.raises(ValueError):
        dc_cable_delivery(**BASE, minimum_voltage_fraction=fraction)
