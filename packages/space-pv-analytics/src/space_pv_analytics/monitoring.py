"""Known-noise log-power trends and degradation monitoring campaign design.

Inputs must be maximum-power measurements normalized to matched illumination,
cell temperature and electrical boundary. These routines do not perform that
physical normalization or infer a radiation damage mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class MonitoringDesign:
    """Conditional Gaussian detection capability; annual losses are fractions."""

    observations: int
    duration_days: float
    slope_standard_error_per_year: float
    minimum_detectable_annual_loss: float
    confidence: float
    detection_probability: float
    drift_bound_per_year: float


@dataclass(frozen=True)
class LogPowerTrend:
    """Log-power slope and drift-expanded confidence interval, in year⁻¹."""

    slope_per_year: float
    slope_lower_per_year: float
    slope_upper_per_year: float
    annual_loss_fraction: float
    loss_detected: bool


def _times(time_days: ArrayLike) -> np.ndarray:
    t = np.asarray(time_days, dtype=float)
    if t.ndim != 1 or len(t) < 3 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError("time_days must contain at least three finite, increasing times")
    return t


def log_power_covariance(
    time_days: ArrayLike,
    *,
    independent_sigma: float,
    correlated_sigma: float = 0.0,
    correlation_days: float = 7.0,
) -> np.ndarray:
    """Construct log-power covariance: white noise plus an exponential kernel.

    Sigmas are standard deviations in natural-log power (dimensionless), not
    percentage points. They approximate relative errors only for small noise.
    The kernel is a declared planning assumption, not a fitted instrument model.
    """
    t = _times(time_days)
    values = [independent_sigma, correlated_sigma, correlation_days]
    if (
        not np.isfinite(values).all()
        or independent_sigma <= 0
        or correlated_sigma < 0
        or correlation_days <= 0
    ):
        raise ValueError(
            "Require positive independent_sigma/correlation_days and nonnegative correlated_sigma"
        )
    return independent_sigma**2 * np.eye(len(t)) + correlated_sigma**2 * np.exp(
        -np.abs(t[:, None] - t[None, :]) / correlation_days
    )


def _regression(time_days: ArrayLike, covariance: ArrayLike) -> tuple[np.ndarray, float]:
    t = _times(time_days)
    c = np.asarray(covariance, dtype=float)
    if c.shape != (len(t), len(t)) or not np.isfinite(c).all():
        raise ValueError("covariance must be finite with shape (observations, observations)")
    if not np.allclose(c, c.T, rtol=1e-10, atol=1e-14):
        raise ValueError("covariance must be symmetric")
    try:
        np.linalg.cholesky(c)
    except np.linalg.LinAlgError as exc:
        raise ValueError("covariance must be positive definite") from exc
    x = np.column_stack([np.ones(len(t)), (t - t.mean()) / 365.25])
    weighted_x = np.linalg.solve(c, x)
    parameter_covariance = np.linalg.inv(x.T @ weighted_x)
    estimator = parameter_covariance @ weighted_x.T
    return estimator, float(np.sqrt(parameter_covariance[1, 1]))


def _critical(confidence: float, drift_bound_per_year: float) -> float:
    if (
        not np.isfinite([confidence, drift_bound_per_year]).all()
        or not 0 < confidence < 1
        or drift_bound_per_year < 0
    ):
        raise ValueError("Require confidence in (0, 1) and finite nonnegative drift bound")
    return NormalDist().inv_cdf((1 + confidence) / 2)


def design_degradation_monitoring(
    time_days: ArrayLike,
    covariance: ArrayLike,
    *,
    confidence: float = 0.95,
    detection_probability: float = 0.8,
    drift_bound_per_year: float = 0.0,
) -> MonitoringDesign:
    """Plan detection of a negative constant log-power slope with known noise.

    GLS covariance is ``(X.T @ C^-1 @ X)^-1``. Reject zero slope when the
    two-sided confidence interval's upper endpoint is negative. For a bounded
    unknown linear calibration drift ±d, the interval expands by d. Guaranteeing
    the requested detection probability at the worst opposing drift requires a
    loss magnitude of ``(z_confidence + z_probability) * slope_se + 2*d``.
    Annual retained power is exp(slope); loss is 1-exp(slope).

    This is conditional on known Gaussian covariance and a constant physical
    slope. It is not a qualification or a forecast of perovskite lifetime.
    """
    z = _critical(confidence, drift_bound_per_year)
    if not np.isfinite(detection_probability) or not 0.5 < detection_probability < 1:
        raise ValueError("detection_probability must be in (0.5, 1)")
    _, se = _regression(time_days, covariance)
    magnitude = (z + NormalDist().inv_cdf(detection_probability)) * se + 2 * drift_bound_per_year
    t = _times(time_days)
    return MonitoringDesign(
        len(t),
        float(t[-1] - t[0]),
        se,
        float(-np.expm1(-magnitude)),
        confidence,
        detection_probability,
        drift_bound_per_year,
    )


def fit_log_power_trend(
    time_days: ArrayLike,
    normalized_power: ArrayLike,
    covariance: ArrayLike,
    *,
    confidence: float = 0.95,
    drift_bound_per_year: float = 0.0,
) -> LogPowerTrend:
    """Fit one normalized device series with externally supplied log covariance.

    No residual variance rescaling is performed: covariance must come from
    calibration/replicates or an explicitly labeled scenario. Do not combine
    devices, eclipse samples, bus-load-limited power, or unmatched IV sweeps.
    Confidence bounds include a bounded linear drift but not normalization bias,
    nonlinear aging, hysteresis, recovery, seasonality or unmodeled change points.
    """
    z = _critical(confidence, drift_bound_per_year)
    estimator, se = _regression(time_days, covariance)
    power = np.asarray(normalized_power, dtype=float)
    if power.shape != (estimator.shape[1],) or not np.isfinite(power).all() or np.any(power <= 0):
        raise ValueError("normalized_power must be finite, positive and match time_days")
    slope = float((estimator @ np.log(power))[1])
    half_width = z * se + drift_bound_per_year
    return LogPowerTrend(
        slope,
        slope - half_width,
        slope + half_width,
        float(-np.expm1(slope)),
        slope + half_width < 0,
    )
