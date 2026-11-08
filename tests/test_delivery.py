import numpy as np
import pytest

from orbitalpv.delivery import assess_delivery, delivery_chain


def test_irregular_intervals_conserve_energy_and_use_duration():
    r = assess_delivery([0, 1, 4, 6], [20, 0, 10], 10, energy_target_wh=40)
    assert r.delivered_wh == 40
    assert r.required_wh == 60
    assert r.shortfall_wh == 30
    assert r.surplus_wh == 10
    assert r.served_wh + r.shortfall_wh == r.required_wh
    assert r.served_wh + r.surplus_wh == r.delivered_wh
    assert r.availability == 0.5
    assert r.longest_shortfall_h == 3
    assert r.largest_event_shortfall_wh == 30
    assert r.energy_target_met


def test_equal_energy_different_backup_events():
    a = assess_delivery(np.arange(5), [0, 0, 20, 20], 10, energy_target_wh=40)
    b = assess_delivery(np.arange(5), [0, 20, 0, 20], 10, energy_target_wh=40)
    assert a.delivered_wh == b.delivered_wh
    assert a.availability == b.availability == 0.5
    assert a.largest_event_shortfall_wh == 2 * b.largest_event_shortfall_wh
    assert a.backup_peak_w == b.backup_peak_w == 10


def test_tolerance_changes_classification_not_energy():
    r = assess_delivery([0, 1], 9.99, 10, energy_target_wh=10, tolerance_w=0.02)
    assert r.availability == 1
    assert r.shortfall_wh == pytest.approx(0.01)
    assert not r.energy_target_met


def test_stage_loss_and_zero_efficiency():
    r = delivery_chain([100, 200], {"rf": 0.5, "grid": 0.8})
    np.testing.assert_allclose(r.grid, [40, 80])
    assert (r.diff(axis=1).iloc[:, 1:] <= 0).all().all()
    assert delivery_chain([100], {"rf": 0}).rf.iloc[0] == 0


@pytest.mark.parametrize("edges", [[0], [0, 0], [1, 0], [0, np.nan]])
def test_bad_edges(edges):
    with pytest.raises(ValueError):
        assess_delivery(edges, 1, 1, energy_target_wh=1)


@pytest.mark.parametrize("power", [[1, 2], -1, np.nan, np.inf])
def test_bad_power(power):
    with pytest.raises(ValueError):
        assess_delivery([0, 1], power, 1, energy_target_wh=1)


@pytest.mark.parametrize("efficiency", [-0.1, 1.1, np.nan, np.inf])
def test_bad_efficiency(efficiency):
    with pytest.raises(ValueError):
        delivery_chain([100], {"grid": efficiency})


def test_all_outage_and_no_outage_boundaries():
    a = assess_delivery([0, 2, 5], 0, [10, 20], energy_target_wh=80)
    assert a.availability == 0
    assert a.largest_event_shortfall_wh == 80
    assert a.longest_shortfall_h == 5
    b = assess_delivery([0, 5], 10, 10, energy_target_wh=50)
    assert b.availability == 1
    assert b.shortfall_wh == b.longest_shortfall_h == b.backup_peak_w == 0
