"""Known synthetic cloud motion, missing-support and forecast issue-time checks."""

from typing import Any

import numpy as np
import pytest

pytest.importorskip("scipy")

from orbitalpv.ground_forecasting import (
    CloudMotion,
    advect_cloud_field,
    blend_irradiance_forecasts,
    clear_sky_persistence,
    estimate_cloud_motion,
    evaluate_irradiance_forecast,
    forecast_irradiance,
)


def _cloud():
    from scipy.ndimage import gaussian_filter

    return 0.3 + 0.7 * gaussian_filter(np.random.default_rng(77).random((64, 64)), 1.3)


def test_clear_sky_persistence_broadcast_night_and_enhancement():
    assert float(clear_sky_persistence(300, 600, 800)) == 400
    assert float(clear_sky_persistence(0, 0, 0)) == 0
    assert np.ma.is_masked(clear_sky_persistence(0, 0, 800))
    predicted = clear_sky_persistence([300, 0, 900], [600, 0, 500], [[800, 800, 800], [0, 0, 0]])
    assert predicted[0, 0] == 400
    assert np.ma.getmaskarray(predicted)[0, 1]
    assert predicted[0, 2] == 1_200
    np.testing.assert_array_equal(predicted[1], [0, 0, 0])
    with pytest.raises(ValueError, match="nonnegative"):
        clear_sky_persistence(-1, 500, 800)


@pytest.mark.parametrize("method", ["phase_correlation", "lucas_kanade"])
def test_cloud_translation_sign_time_units_and_missing_inflow(method):
    previous = _cloud()
    current = np.roll(previous, (2, -3), axis=(0, 1))
    motion = estimate_cloud_motion(
        previous, current, minutes_between=10, method=method, max_shift_pixels=10
    )
    assert motion.quality["global_row_shift_pixels"] == 2
    assert motion.quality["global_column_shift_pixels"] == -3
    assert np.median(motion.row_pixels_per_minute) == pytest.approx(0.2, abs=0.01)
    assert np.median(motion.column_pixels_per_minute) == pytest.approx(-0.3, abs=0.01)
    prediction = advect_cloud_field(current, motion, lead_minutes=10)
    expected = np.roll(current, (2, -3), axis=(0, 1))
    np.testing.assert_allclose(prediction[8:-8, 8:-8], expected[8:-8, 8:-8], atol=0.006)
    assert np.ma.getmaskarray(prediction)[:2].any()
    assert np.ma.getmaskarray(prediction)[:, -3:].any()
    assert not np.ma.getmaskarray(prediction)[10:-10, 10:-10].any()


def test_dense_optical_flow_improves_fractional_shift_over_integer_baseline():
    from scipy.ndimage import shift

    previous = _cloud()
    current = shift(previous, (0.4, 1.3), order=1, mode="nearest")
    dense = estimate_cloud_motion(
        previous, current, minutes_between=5, method="lucas_kanade", max_shift_pixels=8
    )
    phase = estimate_cloud_motion(
        previous, current, minutes_between=5, method="phase_correlation", max_shift_pixels=8
    )
    target = np.array([0.4, 1.3]) / 5
    estimated = np.array(
        [
            np.median(dense.row_pixels_per_minute[8:-8, 8:-8]),
            np.median(dense.column_pixels_per_minute[8:-8, 8:-8]),
        ]
    )
    phase_estimated = np.array([phase.row_pixels_per_minute, phase.column_pixels_per_minute])
    assert np.linalg.norm(estimated - target) < np.linalg.norm(phase_estimated - target)
    assert dense.quality["locally_refined_fraction"] > 0.5


def test_flat_field_and_invalid_time_do_not_invent_motion():
    with pytest.raises(ValueError, match="texture"):
        estimate_cloud_motion(np.ones((20, 20)), np.ones((20, 20)), minutes_between=5)
    with pytest.raises(ValueError, match="minutes_between"):
        estimate_cloud_motion(_cloud(), _cloud(), minutes_between=0)
    with pytest.raises(ValueError, match="lead_minutes"):
        advect_cloud_field(_cloud(), CloudMotion(1, 0, 5, "fixture", {}), lead_minutes=-1)


def test_nowcast_units_leads_provenance_and_skill():
    old = _cloud()
    current = np.roll(old, (0, 2), axis=(0, 1))
    clear = np.full((2, 64, 64), 800.0)
    result = forecast_irradiance(
        old,
        current,
        clear,
        minutes_between=5,
        lead_minutes=[0, 5],
        source="synthetic known-advection fixture",
        license_name="CC0",
        method="phase_correlation",
    )
    np.testing.assert_allclose(result.ghi_wm2[0], current * 800)
    truth = np.roll(current, (0, 2), axis=(0, 1)) * 800
    score = evaluate_irradiance_forecast(result.ghi_wm2[1], truth, persistence=current * 800)
    assert score["rmse_wm2"] < 1e-9
    assert score["rmse_skill_vs_persistence"] == pytest.approx(1)
    assert result.metadata["license"] == "CC0"
    assert result.metadata["inferred"]


def test_weather_fusion_rejects_hindsight_and_uses_available_source():
    short = np.array([[400, np.nan], [400, 400]])
    weather = np.array([[800, 800], [800, np.nan]])
    arguments: dict[str, Any] = {
        "lead_minutes": [0, 120],
        "forecast_origin": "2026-01-01T10:00Z",
        "weather_issue_time": "2026-01-01T06:00Z",
    }
    mixed = blend_irradiance_forecasts(short, weather, **arguments)
    assert mixed[0, 0] == 400
    assert mixed[0, 1] == 800
    assert mixed[1, 0] == pytest.approx(400 * np.exp(-1) + 800 * (1 - np.exp(-1)))
    assert mixed[1, 1] == 400
    with pytest.raises(ValueError, match="reanalysis"):
        blend_irradiance_forecasts(short, weather, weather_kind="reanalysis", **arguments)
    future_arguments: dict[str, Any] = {**arguments, "weather_issue_time": "2026-01-01T12:00Z"}
    with pytest.raises(ValueError, match="no later"):
        blend_irradiance_forecasts(short, weather, **future_arguments)


def test_forecast_metrics_share_support_with_persistence():
    result = evaluate_irradiance_forecast([0, 1, 100], [0, 0, 0], persistence=[2, 2, np.nan])
    assert result["n"] == 2
    assert result["rmse_wm2"] == pytest.approx(np.sqrt(0.5))
    assert result["persistence_rmse_wm2"] == 2
