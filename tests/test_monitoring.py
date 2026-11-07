"""Analytic regression checks and simulated statistical operating characteristics."""

from statistics import NormalDist

import numpy as np
import pytest

from orbitalpv.analytics import (
    design_degradation_monitoring,
    fit_log_power_trend,
    log_power_covariance,
)


def test_independent_closed_form_and_time_origin():
    times = np.arange(0, 365, 7)
    covariance = log_power_covariance(times, independent_sigma=0.02)
    design = design_degradation_monitoring(times, covariance)
    expected_se = 0.02 / np.sqrt(np.sum(((times - times.mean()) / 365.25) ** 2))
    assert design.slope_standard_error_per_year == pytest.approx(expected_se)
    assert design == design_degradation_monitoring(times + 10000, covariance)
    power = 3.0 * np.exp(-0.07 * times / 365.25)
    fit = fit_log_power_trend(times, power, covariance)
    assert fit.slope_per_year == pytest.approx(-0.07)
    assert fit.annual_loss_fraction == pytest.approx(1 - np.exp(-0.07))
    assert fit.loss_detected
    assert fit_log_power_trend(times, power * 12, covariance).slope_per_year == pytest.approx(-0.07)


def test_constant_common_gain_does_not_reduce_slope_information():
    times = np.arange(20, dtype=float)
    covariance = log_power_covariance(times, independent_sigma=0.02)
    baseline = design_degradation_monitoring(times, covariance)
    shared_gain = design_degradation_monitoring(times, covariance + 0.1**2)
    assert shared_gain.slope_standard_error_per_year == pytest.approx(
        baseline.slope_standard_error_per_year
    )


def test_correlated_noise_and_drift_degrade_capability():
    times = np.arange(0, 365, 7)
    white = log_power_covariance(times, independent_sigma=0.02)
    correlated = log_power_covariance(times, independent_sigma=0.02, correlated_sigma=0.03)
    a = design_degradation_monitoring(times, white)
    b = design_degradation_monitoring(times, correlated)
    c = design_degradation_monitoring(times, correlated, drift_bound_per_year=0.01)
    assert (
        a.minimum_detectable_annual_loss
        < b.minimum_detectable_annual_loss
        < c.minimum_detectable_annual_loss
    )
    assert c.minimum_detectable_annual_loss == pytest.approx(0.0787605489)


def test_monte_carlo_worst_case_drift_coverage_and_detection():
    # Independently whiten synthetic raw log-observations and solve with lstsq.
    times = np.arange(0, 183, 7)
    covariance = log_power_covariance(times, independent_sigma=0.02, correlated_sigma=0.03)
    drift = 0.01
    design = design_degradation_monitoring(times, covariance, drift_bound_per_year=drift)
    magnitude = -np.log1p(-design.minimum_detectable_annual_loss)
    rng = np.random.default_rng(8107)
    cholesky = np.linalg.cholesky(covariance)
    noise = cholesky @ rng.normal(size=(len(times), 20000))
    x = np.column_stack([np.ones(len(times)), times / 365.25])
    # Opposing drift gives worst detection probability for physical slope < 0.
    y = x[:, 1, None] * (-magnitude + drift) + noise
    estimates = np.linalg.lstsq(
        np.linalg.solve(cholesky, x), np.linalg.solve(cholesky, y), rcond=None
    )[0][1]
    half_width = NormalDist().inv_cdf(0.975) * design.slope_standard_error_per_year + drift
    assert np.mean(estimates + half_width < 0) == pytest.approx(0.8, abs=0.012)
    assert np.mean(np.abs(estimates + magnitude) <= half_width) >= 0.95
    # At zero physical trend, worst negative drift preserves the 2.5% tail.
    null_estimates = estimates + magnitude - 2 * drift
    assert np.mean(null_estimates + half_width < 0) == pytest.approx(0.025, abs=0.005)


@pytest.mark.parametrize("times", [[0, 1], [0, 0, 1], [2, 1, 0], [0, 1, np.nan], [[0, 1, 2]]])
def test_invalid_times(times):
    with pytest.raises(ValueError, match="time_days"):
        log_power_covariance(times, independent_sigma=0.02)


@pytest.mark.parametrize(
    "covariance",
    [np.eye(2), np.zeros((3, 3)), [[1, 1, 0], [0, 1, 0], [0, 0, 1]], np.full((3, 3), np.nan)],
)
def test_invalid_covariance(covariance):
    with pytest.raises(ValueError, match="covariance"):
        design_degradation_monitoring([0, 1, 2], covariance)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"confidence": 1},
        {"detection_probability": 0.5},
        {"drift_bound_per_year": -1},
        {"drift_bound_per_year": np.nan},
    ],
)
def test_invalid_design_parameters(kwargs):
    with pytest.raises(ValueError):
        design_degradation_monitoring([0, 1, 2], np.eye(3), **kwargs)


@pytest.mark.parametrize("power", [[1, 0, 1], [1, -1, 1], [1, np.inf, 1], [1, 2]])
def test_invalid_power(power):
    with pytest.raises(ValueError, match="normalized_power"):
        fit_log_power_trend([0, 1, 2], power, np.eye(3))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"independent_sigma": 0},
        {"independent_sigma": np.nan},
        {"independent_sigma": 0.02, "correlated_sigma": -1},
        {"independent_sigma": 0.02, "correlation_days": 0},
    ],
)
def test_invalid_noise(kwargs):
    with pytest.raises(ValueError):
        log_power_covariance([0, 1, 2], **kwargs)
