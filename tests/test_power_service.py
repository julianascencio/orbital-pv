import pytest

from orbitalpv.physics import BatterySpec
from orbitalpv.utility import screen_power_service


def test_dark_energy_bound_and_delivery_losses():
    battery = BatterySpec(120000, initial_soc=0.9, minimum_soc=0.2, maximum_soc=0.95)
    result = screen_power_service(
        [0, 400 * 3600, 520 * 3600],
        [0, 2000],
        50,
        [2, 3],
        customer_power_w=50,
        delivery_efficiency=0.9,
        battery=battery,
    )
    assert result.repeatable_profile_feasible.tolist() == [True, False]
    available = 120000 * 0.7 * 0.95
    expected_shortfall = (50 + 150 / 0.9) * 400 - available
    assert result.unserved_bus_wh.iloc[1] == pytest.approx(expected_shortfall)


def test_survival_does_not_imply_repeatability():
    result = screen_power_service(
        [0, 3600],
        [0],
        0,
        [0, 1],
        customer_power_w=10,
        delivery_efficiency=1,
        battery=BatterySpec(100),
    )
    assert result.finite_horizon_feasible.tolist() == [True, True]
    assert result.repeatable_profile_feasible.tolist() == [True, False]


def test_housekeeping_failure_rejects_zero_customers():
    result = screen_power_service(
        [0, 3600],
        [0],
        1000,
        [0],
        customer_power_w=1,
        delivery_efficiency=1,
        battery=BatterySpec(100),
    )
    assert not result.finite_horizon_feasible.iloc[0]


@pytest.mark.parametrize(
    "counts,efficiency,power",
    [
        ([], 1, 1),
        ([True], 1, 1),
        ([-1], 1, 1),
        ([1, 1], 1, 1),
        ([1], 0, 1),
        ([1], 1.1, 1),
        ([1], 1, float("nan")),
    ],
)
def test_invalid_contracts(counts, efficiency, power):
    with pytest.raises(ValueError):
        screen_power_service(
            [0, 3600],
            [10],
            0,
            counts,
            customer_power_w=power,
            delivery_efficiency=efficiency,
            battery=BatterySpec(100),
        )
