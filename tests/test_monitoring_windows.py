import pandas as pd
import pytest

from orbitalpv.monitoring_windows import forecast_monitoring_windows, monitoring_sample_budget


def inputs():
    return pd.DataFrame(
        {
            "method": ["a", "b"],
            "submitted_utc": ["2026-01-01T00:00Z"] * 2,
            "arrival_utc": ["2026-01-02T00:00Z", "2026-01-02T02:00Z"],
            "before_hours": [1, 1],
            "after_hours": [1, 1],
        }
    )


def test_touching_union_and_budget():
    windows, _ = forecast_monitoring_windows(inputs(), as_of_utc="2026-01-01T12:00Z")
    assert len(windows) == 1
    assert monitoring_sample_budget(windows, cadence_s=60, bytes_per_sample=256) == {
        "monitoring_hours": 4,
        "samples": 240,
        "bytes": 61440,
    }


def test_future_submission_excluded_and_cutoff_clips():
    data = inputs()
    data.loc[1, "submitted_utc"] = "2026-01-03T00:00Z"
    windows, eligible = forecast_monitoring_windows(data, as_of_utc="2026-01-02T00:00Z")
    assert len(eligible) == 1
    assert monitoring_sample_budget(windows, cadence_s=3600, bytes_per_sample=1)["samples"] == 1


def test_missing_uncertainty_is_not_zero():
    data = inputs()
    data.loc[0, "before_hours"] = float("nan")
    with pytest.raises(ValueError, match="Missing bounds"):
        forecast_monitoring_windows(data, as_of_utc="2026-01-01T12:00Z")
    _, eligible = forecast_monitoring_windows(
        data, as_of_utc="2026-01-01T12:00Z", missing_bound_hours=12
    )
    assert eligible.assumed_bound.tolist() == [True, False]


def test_gaps_and_partial_cadences():
    data = inputs()
    data.loc[1, "arrival_utc"] = "2026-01-03T00:00Z"
    windows, _ = forecast_monitoring_windows(data, as_of_utc="2026-01-01T12:00Z")
    assert len(windows) == 2
    assert monitoring_sample_budget(windows, cadence_s=5000, bytes_per_sample=1)["samples"] == 4


@pytest.mark.parametrize("change", ["naive", "negative", "duplicate"])
def test_invalid_forecasts(change):
    data = inputs()
    if change == "naive":
        data["arrival_utc"] = "2026-01-02"
    if change == "negative":
        data["before_hours"] = -1
    if change == "duplicate":
        data["method"] = "a"
    with pytest.raises(ValueError):
        forecast_monitoring_windows(data, as_of_utc="2026-01-01T12:00Z")
