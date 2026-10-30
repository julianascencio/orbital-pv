"""Traceable linear calibration and measured electrical energy reconciliation.

The Gaussian posterior below is a conjugate Bayesian linear model with a
caller-supplied observation noise. It is not a Gaussian process, a neural
network, or a reproduction of a spacecraft digital-twin paper.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal

import numpy as np
import pandas as pd

Purpose = Literal["healthy_reference", "operating_forecast"]


def _finite_matrix(values, name: str) -> np.ndarray:
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix[:, None]
    if matrix.ndim != 2 or not len(matrix) or not matrix.shape[1] or not np.isfinite(matrix).all():
        raise ValueError(f"{name} must be a nonempty finite vector or 2D matrix")
    return matrix


def _time_index(values, *, name: str = "timestamps") -> pd.DatetimeIndex:
    times = pd.DatetimeIndex(values)
    if not len(times) or times.hasnans or not times.is_monotonic_increasing or times.has_duplicates:
        raise ValueError(f"{name} must be nonempty, valid, strictly increasing timestamps")
    return times.as_unit("ns")


def _purpose(purpose: Purpose, evidence: str) -> None:
    if purpose not in {"healthy_reference", "operating_forecast"}:
        raise ValueError("purpose must distinguish healthy_reference from operating_forecast")
    if purpose == "healthy_reference" and not evidence.strip():
        raise ValueError(
            "A healthy reference requires a description of independent health evidence"
        )


@dataclass(frozen=True)
class LinearCalibration:
    """A ridge/least-squares fit with training-only feature normalization."""

    coefficients: np.ndarray
    feature_mean: np.ndarray
    feature_scale: np.ndarray
    trained_from: pd.Timestamp
    trained_through: pd.Timestamp
    purpose: Purpose
    evidence: str
    samples: int

    def design(self, features) -> np.ndarray:
        values = _finite_matrix(features, "features")
        if values.shape[1] != len(self.feature_mean):
            raise ValueError("Prediction feature count differs from fitted feature count")
        return np.column_stack(
            [np.ones(len(values)), (values - self.feature_mean) / self.feature_scale]
        )

    def predict(self, features, *, timestamps=None, held_out: bool = True) -> np.ndarray:
        """Predict; supplied held-out timestamps must follow all fit labels.

        Omit timestamps only for algebraic/in-sample model inspection. A caller
        doing an evaluation should always supply them; no function can discover
        hidden future information in caller-constructed feature columns.
        """
        design = self.design(features)
        if timestamps is not None:
            times = _time_index(timestamps)
            if len(times) != len(design):
                raise ValueError("Prediction timestamps and features have different lengths")
            if held_out and times[0] <= self.trained_through:
                raise ValueError("Held-out predictions must follow the training label window")
        return design @ self.coefficients


def fit_linear_calibration(
    features,
    target,
    *,
    timestamps,
    purpose: Purpose,
    evidence: str = "",
    ridge: float = 0.0,
) -> LinearCalibration:
    """Fit a deterministic reference or forecast, declaring its intended role.

    ``timestamps`` identify target/label times, including the last forecast
    horizon. The intercept is unpenalized. Ridge is in standardized-feature
    coordinates; this is a statistical baseline, not an inferred physical law.
    """
    _purpose(purpose, evidence)
    x, y = _finite_matrix(features, "features"), _finite_matrix(target, "target")
    times = _time_index(timestamps)
    if len(x) != len(y) or len(x) != len(times):
        raise ValueError("Training features, targets and timestamps must have equal lengths")
    if not np.isfinite(ridge) or ridge < 0:
        raise ValueError("ridge must be finite and non-negative")
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale > np.finfo(float).eps, scale, 1.0)
    design = np.column_stack([np.ones(len(x)), (x - center) / scale])
    if ridge:
        penalty = np.sqrt(ridge) * np.eye(design.shape[1])
        penalty[0, 0] = 0
        design_fit = np.vstack([design, penalty])
        y_fit = np.vstack([y, np.zeros((design.shape[1], y.shape[1]))])
    else:
        design_fit, y_fit = design, y
    weights = np.linalg.lstsq(design_fit, y_fit, rcond=None)[0]
    return LinearCalibration(weights, center, scale, times[0], times[-1], purpose, evidence, len(x))


@dataclass(frozen=True)
class BayesianLinearCalibration:
    """Normal likelihood + zero-mean normal coefficient prior, known noise."""

    model: LinearCalibration
    coefficient_covariance: np.ndarray
    observation_noise_std: float
    prior_std: float

    def predict(
        self,
        features,
        *,
        timestamps=None,
        coverage: float = 0.95,
        include_observation_noise: bool = True,
    ) -> pd.DataFrame:
        """Return posterior mean and Gaussian credible/predictive intervals.

        Coverage is a model-based probability, not verified frequentist coverage.
        Future model discrepancy and parameter drift are not included.
        """
        if not 0 < coverage < 1:
            raise ValueError("coverage must lie strictly between zero and one")
        mean = self.model.predict(features, timestamps=timestamps)[:, 0]
        design = self.model.design(features)
        variance = np.einsum("ij,jk,ik->i", design, self.coefficient_covariance, design)
        if include_observation_noise:
            variance += self.observation_noise_std**2
        std = np.sqrt(np.maximum(variance, 0))
        width = NormalDist().inv_cdf((1 + coverage) / 2) * std
        return pd.DataFrame(
            {"mean": mean, "std": std, "lower": mean - width, "upper": mean + width}
        )


def fit_bayesian_linear_calibration(
    features,
    target,
    *,
    timestamps,
    purpose: Purpose,
    observation_noise_std: float,
    prior_std: float = 10.0,
    evidence: str = "",
) -> BayesianLinearCalibration:
    """Compute an exact Gaussian coefficient posterior with explicit noise/prior.

    Prior standard deviation applies to all coefficients, including intercept,
    in standardized feature coordinates and the target's units. Choose noise
    on training data or independent calibration evidence, never evaluation data.
    """
    if not np.isfinite(observation_noise_std) or observation_noise_std <= 0:
        raise ValueError("observation_noise_std must be finite and positive")
    if not np.isfinite(prior_std) or prior_std <= 0:
        raise ValueError("prior_std must be finite and positive")
    base = fit_linear_calibration(
        features, target, timestamps=timestamps, purpose=purpose, evidence=evidence
    )
    y = _finite_matrix(target, "target")
    if y.shape[1] != 1:
        raise ValueError("Bayesian calibration currently supports one target")
    design = base.design(features)
    precision = (
        design.T @ design / observation_noise_std**2 + np.eye(design.shape[1]) / prior_std**2
    )
    covariance = np.linalg.solve(precision, np.eye(precision.shape[0]))
    covariance = (covariance + covariance.T) / 2
    coefficients = np.linalg.solve(precision, design.T @ y / observation_noise_std**2)
    model = LinearCalibration(
        coefficients,
        base.feature_mean,
        base.feature_scale,
        base.trained_from,
        base.trained_through,
        purpose,
        evidence,
        base.samples,
    )
    return BayesianLinearCalibration(model, covariance, observation_noise_std, prior_std)


@dataclass(frozen=True)
class MeasuredEnergyBudget:
    """Energy integrated over common valid observation intervals only."""

    intervals: pd.DataFrame
    summary: dict[str, float | int | str]


def measured_energy_budget(
    frame: pd.DataFrame,
    *,
    solar_column: str = "solar_bus_power_w",
    load_column: str = "bus_power_w",
    battery_column: str | None = None,
    battery_discharge_sign: int = 1,
    max_gap_s: float,
) -> MeasuredEnergyBudget:
    """Reconcile solar + battery discharge - load using common valid intervals.

    A residual is unexplained measurement/boundary mismatch, not an attributed
    physical loss. Supply battery sign explicitly when source data use charge-
    positive current. Missing battery telemetry is not assumed to be zero unless
    the caller chooses ``battery_column=None`` (a solar-versus-load comparison).
    Multiplexed group rows require a separately justified alignment first.
    """
    if frame.attrs.get("schema") == "multiplexed":
        raise ValueError(
            "Multiplexed channels need explicit group alignment before energy accounting"
        )
    if not np.isfinite(max_gap_s) or max_gap_s <= 0:
        raise ValueError("max_gap_s must be finite and positive")
    if battery_discharge_sign not in {-1, 1}:
        raise ValueError("battery_discharge_sign must be -1 or +1")
    columns = [solar_column, load_column] + ([] if battery_column is None else [battery_column])
    missing = {"timestamp", *columns} - set(frame.columns)
    if missing:
        raise ValueError(f"Missing energy budget columns: {sorted(missing)}")
    times = _time_index(frame["timestamp"])
    if len(times) < 2:
        raise ValueError("Energy integration needs at least two timestamped measurements")
    values = frame[columns].to_numpy(dtype=float)
    duration = np.diff(times.asi8) / 1e9
    valid = np.isfinite(values).all(axis=1)
    accepted = valid[:-1] & valid[1:] & (duration <= max_gap_s)
    solar = (values[:-1, 0] + values[1:, 0]) * duration / 7200
    load = (values[:-1, 1] + values[1:, 1]) * duration / 7200
    battery = (
        np.zeros(len(duration))
        if battery_column is None
        else (battery_discharge_sign * (values[:-1, 2] + values[1:, 2]) * duration / 7200)
    )
    intervals = pd.DataFrame(
        {
            "start": times[:-1],
            "end": times[1:],
            "duration_s": duration,
            "accepted": accepted,
            "solar_wh": np.where(accepted, solar, np.nan),
            "load_wh": np.where(accepted, load, np.nan),
            "battery_discharge_wh": np.where(accepted, battery, np.nan),
            "unexplained_balance_wh": np.where(accepted, solar + battery - load, np.nan),
        }
    )
    observed = float(duration[accepted].sum())
    span = float(duration.sum())
    summary: dict[str, float | int | str] = {
        "observed_duration_h": observed / 3600,
        "timestamp_span_h": span / 3600,
        "coverage_fraction": observed / span,
        "accepted_intervals": int(accepted.sum()),
        "excluded_intervals": int((~accepted).sum()),
        "max_gap_s": float(max_gap_s),
        "solar_wh": float(solar[accepted].sum()),
        "load_wh": float(load[accepted].sum()),
        "battery_discharge_wh": float(battery[accepted].sum()),
        "unexplained_balance_wh": float((solar + battery - load)[accepted].sum()),
        "battery_mode": "not included"
        if battery_column is None
        else f"discharge = {battery_discharge_sign:+d} x source",
        "interpretation": "Observed-time energy; no missing periods filled or physical causes inferred",
    }
    return MeasuredEnergyBudget(intervals, summary)


__all__ = [
    "BayesianLinearCalibration",
    "LinearCalibration",
    "MeasuredEnergyBudget",
    "fit_bayesian_linear_calibration",
    "fit_linear_calibration",
    "measured_energy_budget",
]
