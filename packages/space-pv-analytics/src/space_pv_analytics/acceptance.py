"""Paired panel power acceptance under a declared Gaussian log-error budget."""

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class PowerRetentionAssessment:
    """Dimensionless retention and natural-log standard uncertainties.

    ``accepted`` concerns electrical retention only, not flight qualification.
    ``lower_retention`` is a one-sided bound conditional on the supplied known
    error model, not a posterior probability that this panel conforms.
    """

    observations: int
    retention: float
    lower_retention: float
    minimum_retention: float
    confidence: float
    repeat_mean_log_sigma: float
    differential_calibration_log_sigma: float
    combined_log_sigma: float
    point_estimate_accepted: bool
    accepted: bool


def _assess(
    log_retention: float,
    observations: int,
    *,
    repeat_log_sigma: float,
    before_calibration_log_sigma: float,
    after_calibration_log_sigma: float,
    calibration_correlation: float,
    minimum_retention: float,
    confidence: float,
) -> PowerRetentionAssessment:
    if (
        isinstance(observations, (bool, np.bool_))
        or not isinstance(observations, (int, np.integer))
        or observations < 1
    ):
        raise ValueError("observations must be a positive integer")
    values = [
        log_retention,
        repeat_log_sigma,
        before_calibration_log_sigma,
        after_calibration_log_sigma,
        calibration_correlation,
        minimum_retention,
        confidence,
    ]
    if not np.isfinite(values).all():
        raise ValueError("All inputs must be finite")
    if min(values[1:4]) < 0:
        raise ValueError("Standard uncertainties must be nonnegative")
    if not -1 <= calibration_correlation <= 1:
        raise ValueError("calibration_correlation must be in [-1, 1]")
    if not 0 < minimum_retention <= 1 or not 0.5 < confidence < 1:
        raise ValueError("Require minimum_retention in (0, 1] and confidence in (0.5, 1)")
    repeat = repeat_log_sigma / np.sqrt(observations)
    # Algebraically equivalent to ub² + ua² - 2*rho*ub*ua; avoids
    # cancellation when equal, strongly correlated calibration errors cancel.
    ub, ua = before_calibration_log_sigma, after_calibration_log_sigma
    calibration = np.hypot(
        ub - ua, np.sqrt(2 * (1 - calibration_correlation)) * np.sqrt(ub) * np.sqrt(ua)
    )
    combined = np.hypot(repeat, calibration)
    lower_log = log_retention - NormalDist().inv_cdf(confidence) * combined
    with np.errstate(over="ignore", under="ignore"):
        retention, lower = np.exp([log_retention, lower_log])
    if not np.isfinite([retention, lower, combined]).all() or retention == 0:
        raise ValueError("Inputs exceed representable retention or uncertainty range")
    return PowerRetentionAssessment(
        observations=int(observations),
        retention=float(retention),
        lower_retention=float(lower),
        minimum_retention=minimum_retention,
        confidence=confidence,
        repeat_mean_log_sigma=float(repeat),
        differential_calibration_log_sigma=float(calibration),
        combined_log_sigma=float(combined),
        point_estimate_accepted=bool(log_retention >= np.log(minimum_retention)),
        accepted=bool(lower_log >= np.log(minimum_retention)),
    )


def power_retention_acceptance(
    before_power_w: ArrayLike,
    after_power_w: ArrayLike,
    *,
    repeat_log_sigma: float,
    before_calibration_log_sigma: float,
    after_calibration_log_sigma: float,
    calibration_correlation: float = 0.0,
    minimum_retention: float = 0.95,
    confidence: float = 0.95,
) -> PowerRetentionAssessment:
    """Assess paired Pmax measurements at matched AM0 spectrum and temperature.

    Arrays are positive finite 1-D watts, same length, in matching pair order
    for ONE panel. Retention is exp(mean(log(after)-log(before))). The estimand
    is a common multiplicative retention, not a ratio of arithmetic means.

    Each paired log ratio has independent Gaussian repeat error with KNOWN
    standard deviation ``repeat_log_sigma``. It must come from a separately
    validated error budget, not a small-sample plug-in standard deviation.
    Before/after campaign calibration errors are jointly Gaussian, centered,
    constant across repeats and independent of repeat error. Their supplied
    standard uncertainties and correlation determine differential uncertainty;
    these systematic terms do not shrink with the number of measurements.

    The lower bound is exp(mean_log_ratio - z_confidence * combined_sigma).
    A failed bound means insufficient evidence, not proven panel failure.
    Duplicated rows, drift, unmatched illumination/temperature, different panels
    or uncorrected fixed bias violate the model; this function cannot detect them.
    """
    before, after = np.asarray(before_power_w, dtype=float), np.asarray(after_power_w, dtype=float)
    if (
        before.ndim != 1
        or after.shape != before.shape
        or before.size == 0
        or not np.isfinite(before).all()
        or not np.isfinite(after).all()
        or np.any(before <= 0)
        or np.any(after <= 0)
    ):
        raise ValueError("Require equally sized, nonempty 1-D arrays of positive finite power")
    return _assess(
        float(np.mean(np.log(after) - np.log(before))),
        before.size,
        repeat_log_sigma=repeat_log_sigma,
        before_calibration_log_sigma=before_calibration_log_sigma,
        after_calibration_log_sigma=after_calibration_log_sigma,
        calibration_correlation=calibration_correlation,
        minimum_retention=minimum_retention,
        confidence=confidence,
    )


def plan_power_retention_test(
    expected_retention: float,
    observations: int,
    *,
    repeat_log_sigma: float,
    before_calibration_log_sigma: float,
    after_calibration_log_sigma: float,
    calibration_correlation: float = 0.0,
    minimum_retention: float = 0.95,
    confidence: float = 0.95,
) -> PowerRetentionAssessment:
    """Compute the bound at an assumed point estimate, without inventing samples.

    This is a sensitivity calculation, NOT acceptance probability or assurance
    that the planned experiment will pass. Error assumptions match
    :func:`power_retention_acceptance`; all sigmas are natural-log units.
    """
    if not np.isfinite(expected_retention) or expected_retention <= 0:
        raise ValueError("expected_retention must be positive and finite")
    return _assess(
        float(np.log(expected_retention)),
        observations,
        repeat_log_sigma=repeat_log_sigma,
        before_calibration_log_sigma=before_calibration_log_sigma,
        after_calibration_log_sigma=after_calibration_log_sigma,
        calibration_correlation=calibration_correlation,
        minimum_retention=minimum_retention,
        confidence=confidence,
    )
