"""Scientific invariants: causal splits, coherent intervals and energy balance."""

import numpy as np
import pandas as pd
import pytest

from orbitalpv.flight import (
    calibrate_block_conformal_vi,
    chronological_forecast_split,
    conformal_order_statistic,
    fit_bayesian_linear_calibration,
    fit_linear_calibration,
    fit_linear_vi_forecaster,
    make_lagged_vi_data,
    measured_energy_budget,
    persistence_vi_forecast,
    seasonal_lag_vi_forecast,
)


def test_linear_reference_needs_health_evidence_and_holds_out_labels():
    times = pd.date_range("2024-01-01", periods=30, freq="min", tz="UTC")
    x = np.arange(30.0)
    y = 3 + 2 * x
    with pytest.raises(ValueError, match="health evidence"):
        fit_linear_calibration(x, y, timestamps=times, purpose="healthy_reference")
    model = fit_linear_calibration(
        x, y, timestamps=times, purpose="healthy_reference", evidence="Independent healthy lab run"
    )
    future = pd.date_range(times[-1] + pd.Timedelta(minutes=1), periods=2, freq="min")
    np.testing.assert_allclose(model.predict([30, 31], timestamps=future)[:, 0], [63, 65])
    with pytest.raises(ValueError, match="training label"):
        model.predict([3, 4], timestamps=times[:2])


def test_bayesian_posterior_matches_closed_form_and_uncertainty_components():
    x = np.linspace(-2, 2, 21)
    times = pd.date_range("2024", periods=len(x), freq="h")
    model = fit_bayesian_linear_calibration(
        x,
        4 + 0.5 * x,
        timestamps=times,
        purpose="operating_forecast",
        observation_noise_std=0.2,
        prior_std=7,
    )
    design = model.model.design(x)
    expected_cov = np.linalg.inv(design.T @ design / 0.04 + np.eye(2) / 49)
    np.testing.assert_allclose(model.coefficient_covariance, expected_cov)
    assert np.linalg.eigvalsh(model.coefficient_covariance).min() > 0
    credible = model.predict([0, 10], include_observation_noise=False)
    predictive = model.predict([0, 10], include_observation_noise=True)
    np.testing.assert_allclose(predictive["std"] ** 2 - credible["std"] ** 2, 0.04)
    assert credible["std"].iloc[1] > credible["std"].iloc[0]
    with pytest.raises(ValueError, match="one target"):
        fit_bayesian_linear_calibration(
            x, np.c_[x, x], timestamps=times, purpose="operating_forecast", observation_noise_std=1
        )


def _flight():
    times = pd.date_range("2024", periods=400, freq="30s", tz="UTC")
    t = np.arange(len(times), dtype=float)
    return pd.DataFrame(
        {"timestamp": times, "voltage_v": 12 + 0.02 * t, "current_a": 1 + 0.001 * t}
    )


def test_forecast_lags_are_causal_gaps_excluded_and_boundaries_purged():
    frame = _flight()
    frame.loc[200:, "timestamp"] += pd.Timedelta(minutes=15)
    data = make_lagged_vi_data(frame, lags=(0, 1, 2), horizons=(1, 4), cadence_s=30)
    assert data.source_windows - len(data.features) == 6
    train, cal, test = chronological_forecast_split(
        data, training_stop=frame.timestamp.iloc[120], calibration_stop=frame.timestamp.iloc[270]
    )
    assert train.target_end_times[-1] < cal.origin_times[0]
    assert cal.target_end_times[-1] < test.origin_times[0]
    # Changing a future target cannot alter the feature at an earlier origin.
    original = frame.copy()
    frame.loc[300, "current_a"] = 999
    changed = make_lagged_vi_data(frame, lags=(0, 1, 2), horizons=(1, 4), cadence_s=30)
    before = data.origin_times < original.timestamp.iloc[300]
    np.testing.assert_array_equal(data.features[before], changed.features[before])
    forecaster = fit_linear_vi_forecaster(train, ridge=0)
    np.testing.assert_allclose(forecaster.predict(test), test.targets, atol=1e-10)
    with pytest.raises(ValueError, match="training label"):
        forecaster.predict(train)


def test_persistence_and_orbit_lag_use_only_available_observations():
    frame = _flight()
    data = make_lagged_vi_data(frame, lags=(0, 1, 16, 19), horizons=(1, 4), cadence_s=30)
    baseline = persistence_vi_forecast(data)
    np.testing.assert_array_equal(baseline[:, 0], data.origin_values)
    orbit_lag = seasonal_lag_vi_forecast(data, period_steps=20)
    first_origin = 19
    np.testing.assert_allclose(
        orbit_lag[0, 0],
        frame.loc[first_origin - 19, ["voltage_v", "current_a"]].to_numpy(dtype=float),
    )
    np.testing.assert_allclose(
        orbit_lag[0, 1],
        frame.loc[first_origin - 16, ["voltage_v", "current_a"]].to_numpy(dtype=float),
    )
    with pytest.raises(ValueError, match="largest horizon"):
        seasonal_lag_vi_forecast(data, period_steps=2)
    with pytest.raises(ValueError, match="requires supplied lag"):
        seasonal_lag_vi_forecast(data, period_steps=21)


def test_finite_sample_conformal_quantile_does_not_clip_to_unsupported_rank():
    assert conformal_order_statistic([1, 2, 3, 4], coverage=0.8) == 4
    assert np.isinf(conformal_order_statistic([1, 2, 3, 4], coverage=0.9))
    assert conformal_order_statistic(np.arange(1, 10), coverage=0.9) == 9


def test_joint_vi_blocks_covary_and_power_extrema_include_signed_values():
    origin = pd.date_range("2024-01-02", periods=100, freq="min", tz="UTC")
    end = origin + pd.Timedelta(seconds=30)
    predicted = np.zeros((100, 2, 2))
    actual = predicted.copy()
    # Deliberately correlated V/I residuals, and a bad long-horizon value.
    actual[:, :, 0] = np.arange(100)[:, None] / 100
    actual[:, :, 1] = -actual[:, :, 0]
    actual[10, 1, 1] = 2
    model = calibrate_block_conformal_vi(
        actual,
        predicted,
        origin_times=origin,
        target_end_times=end,
        trained_through="2024-01-01T00:00Z",
        scales=(1, 1),
        coverage=0.8,
        block_size=10,
    )
    assert model.calibration_blocks == 10
    assert model.quantile == pytest.approx(0.99)
    future = pd.date_range("2024-01-03", periods=2, freq="min", tz="UTC")
    intervals = model.predict(np.zeros((2, 2, 2)), origin_times=future)
    np.testing.assert_allclose(intervals.power_lower_w, -(0.99**2))
    np.testing.assert_allclose(intervals.power_upper_w, 0.99**2)
    np.testing.assert_array_equal(intervals.power_prediction_w, 0)
    inside = np.array([[[0.7, -0.8], [0.2, 0.4]], [[-0.6, -0.6], [0.9, 0.9]]])
    assert intervals.empirical_coverage(inside)["joint_power_coverage"] == 1
    with pytest.raises(ValueError, match="calibration target"):
        model.predict(predicted[:2], origin_times=origin[:2])


def test_calibration_cannot_overlap_training_and_insufficient_blocks_unbounded():
    origin = pd.date_range("2024", periods=6, freq="min")
    values = np.ones((6, 1, 2))
    with pytest.raises(ValueError, match="follow training"):
        calibrate_block_conformal_vi(
            values,
            values,
            origin_times=origin,
            target_end_times=origin,
            trained_through=origin[0],
            scales=(1, 1),
            block_size=2,
        )
    model = calibrate_block_conformal_vi(
        values,
        values,
        origin_times=origin,
        target_end_times=origin,
        trained_through="2023",
        scales=(1, 1),
        block_size=2,
    )
    assert np.isinf(model.quantile)
    intervals = model.predict(values[:1], origin_times=["2025"])
    assert np.isneginf(intervals.power_lower_w).all()
    assert np.isposinf(intervals.power_upper_w).all()


def test_energy_balance_uses_common_intervals_signs_and_true_time_units():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01 00:00",
                    "2024-01-01 00:01",
                    "2024-01-01 00:02",
                    "2024-01-01 01:00",
                    "2024-01-01 01:01",
                ]
            ),
            "solar_bus_power_w": [10, 10, np.nan, 10, 10],
            "bus_power_w": [12] * 5,
            "battery": [-2] * 5,
        }
    )
    budget = measured_energy_budget(
        frame, battery_column="battery", battery_discharge_sign=-1, max_gap_s=61
    )
    assert budget.summary["observed_duration_h"] == pytest.approx(2 / 60)
    assert budget.summary["solar_wh"] == pytest.approx(1 / 3)
    assert budget.summary["battery_discharge_wh"] == pytest.approx(4 / 60)
    assert budget.summary["unexplained_balance_wh"] == pytest.approx(0)
    assert budget.summary["excluded_intervals"] == 2
    frame.loc[1, "timestamp"] = frame.timestamp.iloc[0]
    with pytest.raises(ValueError, match="strictly increasing"):
        measured_energy_budget(frame, max_gap_s=60)
    frame.attrs["schema"] = "multiplexed"
    with pytest.raises(ValueError, match="group alignment"):
        measured_energy_budget(frame, max_gap_s=60)
