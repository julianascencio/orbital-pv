import numpy as np
import pandas as pd
import pytest

from orbitalpv.charging import schedule_charging


def jobs():
    return pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "release_slot": [0] * 3,
            "deadline_slot": [6] * 3,
            "duration_slots": [2] * 3,
            "delivered_power_w": [400] * 3,
        }
    )


def test_optimum_hits_energy_lower_bound_and_conserves_energy():
    schedule, trace = schedule_charging([700] * 6, [100] * 6, jobs(), slot_hours=1, efficiency=0.8)
    assert trace.load_w.max() == 600  # average load is a lower bound on any peak
    assert trace.load_w.sum() == 3600
    assert schedule.delivered_energy_wh.sum() == 2400
    assert schedule.start_slot.tolist() == [0, 2, 4]
    assert np.all(schedule.end_slot <= schedule.deadline_slot)


def test_window_forces_overlap_and_zero_pv_is_valid():
    data = jobs()
    data["deadline_slot"] = 2
    _, trace = schedule_charging([0] * 6, [100] * 6, data, slot_hours=0.5, efficiency=1)
    assert trace.deficit_w.max() == 1300


@pytest.mark.parametrize("change", ["duplicate", "window", "fractional", "power"])
def test_invalid_jobs(change):
    data = jobs()
    if change == "duplicate":
        data.loc[1, "id"] = "a"
    if change == "window":
        data["deadline_slot"] = 1
    if change == "fractional":
        data["duration_slots"] = 1.5
    if change == "power":
        data["delivered_power_w"] = -1
    with pytest.raises(ValueError):
        schedule_charging([700] * 6, [100] * 6, data, slot_hours=1, efficiency=0.8)


def test_search_guard_and_bad_efficiency():
    with pytest.raises(ValueError, match="Search"):
        schedule_charging(
            [700] * 6, [100] * 6, jobs(), slot_hours=1, efficiency=0.8, max_combinations=1
        )
    with pytest.raises(ValueError):
        schedule_charging([700] * 6, [100] * 6, jobs(), slot_hours=1, efficiency=0)


def test_variable_sunlight_changes_start():
    data = jobs().iloc[:1].copy()
    data["duration_slots"] = 1
    data["deadline_slot"] = 3
    schedule, trace = schedule_charging([0, 500, 0], [100] * 3, data, slot_hours=1, efficiency=1)
    assert schedule.start_slot.tolist() == [1]
    assert trace.deficit_w.max() == 100
