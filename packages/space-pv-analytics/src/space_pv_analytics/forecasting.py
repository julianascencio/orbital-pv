"""Transparent operating-power forecast baselines with chronological splits."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .calibration import LinearCalibration, _time_index, fit_linear_calibration


@dataclass(frozen=True)
class LaggedVIData:
    """Features available at each origin and future measured V/I targets.

    Array axes are sample, horizon, then (voltage, current). Horizons denote
    source-sample steps; actual origin/end timestamps are retained. No gaps are
    filled and any window containing a large cadence departure is excluded.
    """

    features: np.ndarray
    targets: np.ndarray
    origin_values: np.ndarray
    origin_times: pd.DatetimeIndex
    target_end_times: pd.DatetimeIndex
    feature_names: tuple[str, ...]
    lags: tuple[int, ...]
    horizons: tuple[int, ...]
    cadence_s: float
    source_windows: int

    def take(self, selected) -> LaggedVIData:
        index = np.asarray(selected)
        return LaggedVIData(
            self.features[index],
            self.targets[index],
            self.origin_values[index],
            self.origin_times[index],
            self.target_end_times[index],
            self.feature_names,
            self.lags,
            self.horizons,
            self.cadence_s,
            self.source_windows,
        )


def _steps(values: Sequence[int], *, name: str, minimum: int) -> tuple[int, ...]:
    if not values or any(
        isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < minimum for v in values
    ):
        raise ValueError(f"{name} must contain integers >= {minimum}")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(int(v) for v in values)


def make_lagged_vi_data(
    frame: pd.DataFrame,
    *,
    lags: Sequence[int] = (0, 1, 2),
    horizons: Sequence[int] = (1, 2, 4),
    feature_columns: Sequence[str] = ("voltage_v", "current_a"),
    cadence_s: float,
    cadence_tolerance_s: float = 0.5,
) -> LaggedVIData:
    """Build causal lag features and paired targets, rejecting discontinuities.

    Caller-supplied feature columns must themselves be available at the origin.
    Telemetry from multiple panels must be separated before calling this method.
    """
    lag_steps = _steps(lags, name="lags", minimum=0)
    horizon_steps = _steps(horizons, name="horizons", minimum=1)
    if not np.isfinite(cadence_s) or cadence_s <= 0:
        raise ValueError("cadence_s must be finite and positive")
    if not np.isfinite(cadence_tolerance_s) or not 0 <= cadence_tolerance_s < cadence_s:
        raise ValueError("cadence_tolerance_s must be nonnegative and smaller than cadence_s")
    if not feature_columns or len(set(feature_columns)) != len(feature_columns):
        raise ValueError("feature_columns must be nonempty and unique")
    missing = {"timestamp", "voltage_v", "current_a", *feature_columns} - set(frame.columns)
    if missing:
        raise ValueError(f"Missing forecast columns: {sorted(missing)}")
    times = _time_index(frame["timestamp"])
    values = frame[list(feature_columns)].to_numpy(dtype=float)
    vi = frame[["voltage_v", "current_a"]].to_numpy(dtype=float)
    first, last = max(lag_steps), len(frame) - max(horizon_steps)
    if first >= last:
        raise ValueError("Too few measurements for the requested lags and horizons")
    origins = np.arange(first, last)
    features = np.concatenate([values[origins - lag] for lag in lag_steps], axis=1)
    targets = np.stack([vi[origins + horizon] for horizon in horizon_steps], axis=1)
    durations = np.diff(times.asi8) / 1e9
    bad_step = np.abs(durations - cadence_s) > cadence_tolerance_s
    cumulative_bad = np.r_[0, np.cumsum(bad_step)]
    window_bad = (
        cumulative_bad[origins + max(horizon_steps)] - cumulative_bad[origins - max(lag_steps)]
    )
    selected = (
        (window_bad == 0)
        & np.isfinite(features).all(axis=1)
        & np.isfinite(targets).all(axis=(1, 2))
        & np.isfinite(vi[origins]).all(axis=1)
    )
    if not selected.any():
        raise ValueError("No finite continuous forecast windows at the declared cadence")
    selected_origins = origins[selected]
    return LaggedVIData(
        features[selected],
        targets[selected],
        vi[selected_origins],
        times[selected_origins],
        times[selected_origins + max(horizon_steps)],
        tuple(f"{column}__lag_{lag}" for lag in lag_steps for column in feature_columns),
        lag_steps,
        horizon_steps,
        float(cadence_s),
        len(origins),
    )


def chronological_forecast_split(
    data: LaggedVIData, *, training_stop, calibration_stop
) -> tuple[LaggedVIData, LaggedVIData, LaggedVIData]:
    """Split by clock time and purge targets that cross either boundary.

    Training/calibration labels end strictly before their stop. Subsequent
    origins start at or after the stop; lagged historical observations remain
    allowed because they were already observable at each forecast origin.
    """
    train_stop, cal_stop = pd.Timestamp(training_stop), pd.Timestamp(calibration_stop)
    if train_stop >= cal_stop:
        raise ValueError("training_stop must precede calibration_stop")
    train = data.target_end_times < train_stop
    calibration = (data.origin_times >= train_stop) & (data.target_end_times < cal_stop)
    test = data.origin_times >= cal_stop
    if not train.any() or not calibration.any() or not test.any():
        raise ValueError("All chronological partitions must contain complete forecast windows")
    return data.take(train), data.take(calibration), data.take(test)


def persistence_vi_forecast(data: LaggedVIData) -> np.ndarray:
    """Repeat the last observed operating voltage/current at each horizon."""
    return np.repeat(data.origin_values[:, None, :], len(data.horizons), axis=1)


def seasonal_lag_vi_forecast(data: LaggedVIData, *, period_steps: int) -> np.ndarray:
    """Use a historical seasonal/orbit-lag baseline with explicitly chosen lag.

    A sample period is an empirical assumption, not a propagated orbit. Every
    needed lag (period minus horizon) must be present in ``data``. No future
    values are accessed when a horizon exceeds the chosen period: it raises.
    """
    if (
        isinstance(period_steps, bool)
        or not isinstance(period_steps, int)
        or period_steps < max(data.horizons)
    ):
        raise ValueError("period_steps must be an integer at least the largest horizon")
    result = []
    for horizon in data.horizons:
        lag = period_steps - horizon
        required = [f"{column}__lag_{lag}" for column in ("voltage_v", "current_a")]
        if not set(required) <= set(data.feature_names):
            raise ValueError(
                f"Seasonal forecast requires supplied lag {lag} for voltage and current"
            )
        result.append(data.features[:, [data.feature_names.index(name) for name in required]])
    return np.stack(result, axis=1)


@dataclass(frozen=True)
class LinearVIForecaster:
    """Multi-output ridge baseline trained only on preceding V/I labels."""

    model: LinearCalibration
    horizons: tuple[int, ...]
    feature_names: tuple[str, ...]

    def predict(self, data: LaggedVIData) -> np.ndarray:
        if data.horizons != self.horizons or data.feature_names != self.feature_names:
            raise ValueError("Prediction feature/horizon specification differs from training")
        flat = self.model.predict(data.features, timestamps=data.origin_times)
        return flat.reshape(len(flat), len(self.horizons), 2)


def fit_linear_vi_forecaster(data: LaggedVIData, *, ridge: float = 1.0) -> LinearVIForecaster:
    """Fit a direct multi-horizon, multivariate-lag regression baseline."""
    model = fit_linear_calibration(
        data.features,
        data.targets.reshape(len(data.features), -1),
        timestamps=data.target_end_times,
        purpose="operating_forecast",
        ridge=ridge,
        evidence="Chronological historical operating measurements; not a healthy-power reference",
    )
    return LinearVIForecaster(model, data.horizons, data.feature_names)


__all__ = [
    "LaggedVIData",
    "LinearVIForecaster",
    "chronological_forecast_split",
    "fit_linear_vi_forecaster",
    "make_lagged_vi_data",
    "persistence_vi_forecast",
    "seasonal_lag_vi_forecast",
]
