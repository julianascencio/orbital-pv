from statistics import NormalDist

import numpy as np
import pytest
from scipy.stats import norm

from orbitalpv.acceptance import plan_power_retention_test, power_retention_acceptance

BUDGET = {
    "repeat_log_sigma": 0.01,
    "before_calibration_log_sigma": 0.02,
    "after_calibration_log_sigma": 0.02,
}


def test_independent_covariance_oracle_and_decision():
    before = np.array([10, 20, 30, 40])
    after = before * np.array([0.97, 0.98, 0.99, 0.98])
    result = power_retention_acceptance(before, after, **BUDGET)
    mean = np.log(after / before).mean()
    expected_sigma = np.sqrt(0.01**2 / 4 + 2 * 0.02**2)
    assert result.retention == pytest.approx(np.exp(mean))
    assert result.lower_retention == pytest.approx(np.exp(norm.ppf(0.05, mean, expected_sigma)))
    assert result.point_estimate_accepted
    assert not result.accepted
    scaled = power_retention_acceptance(before * 1000, after * 1000, **BUDGET)
    assert scaled.lower_retention == pytest.approx(result.lower_retention)


def test_common_calibration_cancels_but_unequal_uncertainties_remain():
    common = plan_power_retention_test(0.98, 8, calibration_correlation=1, **BUDGET)
    assert common.differential_calibration_log_sigma == 0
    assert common.accepted
    unequal = plan_power_retention_test(
        0.98, 8, calibration_correlation=1, **{**BUDGET, "after_calibration_log_sigma": 0.03}
    )
    assert unequal.differential_calibration_log_sigma == pytest.approx(0.01)


def test_repeats_do_not_remove_campaign_uncertainty():
    short = plan_power_retention_test(0.98, 1, **BUDGET)
    long = plan_power_retention_test(0.98, 128, **BUDGET)
    floor = 0.98 * np.exp(-NormalDist().inv_cdf(0.95) * np.sqrt(2) * 0.02)
    assert short.lower_retention < long.lower_retention < floor < 0.95
    assert short.differential_calibration_log_sigma == long.differential_calibration_log_sigma
    assert long.repeat_mean_log_sigma == pytest.approx(short.repeat_mean_log_sigma / np.sqrt(128))


def test_boundary_and_higher_confidence():
    budget = dict.fromkeys(BUDGET, 0.0)
    result = plan_power_retention_test(0.95, 1, **budget)
    assert result.accepted
    assert result.lower_retention == pytest.approx(0.95)
    lower = plan_power_retention_test(0.98, 8, confidence=0.99, **BUDGET)
    default = plan_power_retention_test(0.98, 8, **BUDGET)
    assert lower.lower_retention < default.lower_retention


def test_conditional_coverage_with_campaign_shared_errors():
    # Independent simulation generates each campaign's errors ONCE, not n times.
    rng = np.random.default_rng(20261114)
    campaigns, n, true_retention, rho = 100_000, 8, 0.94, 0.5
    calibration = rng.multivariate_normal(
        [0, 0], 0.02**2 * np.array([[1, rho], [rho, 1]]), size=campaigns
    )
    estimate = (
        np.log(true_retention)
        + rng.normal(0, 0.01, size=(campaigns, n)).mean(axis=1)
        + calibration[:, 1]
        - calibration[:, 0]
    )
    design = plan_power_retention_test(true_retention, n, calibration_correlation=rho, **BUDGET)
    lower = np.exp(estimate - norm.ppf(0.95) * design.combined_log_sigma)
    assert np.mean(lower <= true_retention) == pytest.approx(0.95, abs=0.003)


@pytest.mark.parametrize(
    "before,after",
    [
        ([], []),
        ([1], [1, 2]),
        ([[1]], [[1]]),
        ([0], [1]),
        ([1], [-1]),
        ([np.nan], [1]),
        ([1], [np.inf]),
    ],
)
def test_invalid_measurements(before, after):
    with pytest.raises(ValueError):
        power_retention_acceptance(before, after, **BUDGET)


@pytest.mark.parametrize("n", [0, -1, 2.5, True, np.bool_(True)])
def test_invalid_counts(n):
    with pytest.raises(ValueError):
        plan_power_retention_test(0.98, n, **BUDGET)


@pytest.mark.parametrize(
    "key,value",
    [
        ("repeat_log_sigma", -1),
        ("repeat_log_sigma", np.nan),
        ("before_calibration_log_sigma", -0.01),
        ("after_calibration_log_sigma", np.inf),
        ("calibration_correlation", 1.01),
        ("calibration_correlation", -1.01),
        ("minimum_retention", 0),
        ("minimum_retention", 1.01),
        ("confidence", 0.5),
        ("confidence", 1),
        ("expected_retention", 0),
        ("expected_retention", np.inf),
    ],
)
def test_invalid_budget(key, value):
    args = {"expected_retention": 0.98, "observations": 8, **BUDGET, key: value}
    with pytest.raises(ValueError):
        plan_power_retention_test(**args)
