"""Chronological block-conformal V/I envelopes with coherent power bounds.

This is a transparent research baseline inspired by recent spacecraft-envelope
work, not an implementation of its complete algorithm. Exact conformal coverage
requires exchangeable block scores; real spacecraft time series may violate
that assumption. Report held-out coverage and interval width by regime.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import cast

import numpy as np
import pandas as pd

from .calibration import _time_index


def _vi(values, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 2 and array.shape[1] == 2:
        array = array[:, None, :]
    if (
        array.ndim != 3
        or array.shape[2] != 2
        or not array.shape[0]
        or not array.shape[1]
        or not np.isfinite(array).all()
    ):
        raise ValueError(f"{name} must be finite with axes (sample, horizon, voltage/current)")
    return array


def conformal_order_statistic(scores, *, coverage: float) -> float:
    """Finite-sample split-conformal quantile; returns infinity if insufficient.

    The order is ceil((n+1)*coverage), without clipping it to n. Clipping would
    silently advertise a confidence level unsupported by the calibration size.
    """
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("scores must be a nonempty finite nonnegative vector")
    if not 0 < coverage < 1:
        raise ValueError("coverage must lie strictly between zero and one")
    rank = ceil((len(values) + 1) * coverage)
    return float("inf") if rank > len(values) else float(np.partition(values, rank - 1)[rank - 1])


@dataclass(frozen=True)
class VIPredictionIntervals:
    """Joint V/I rectangles and sign-safe extrema of their products."""

    prediction: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    power_prediction_w: np.ndarray
    power_lower_w: np.ndarray
    power_upper_w: np.ndarray
    coverage: float

    def empirical_coverage(self, observed) -> dict[str, float]:
        """Measure simultaneous-horizon coverage, retaining unbounded widths."""
        actual = _vi(observed, "observed")
        if actual.shape != self.prediction.shape:
            raise ValueError("Observed and predicted interval shapes must agree")
        within = (actual >= self.lower) & (actual <= self.upper)
        actual_power = actual[..., 0] * actual[..., 1]
        power_within = (actual_power >= self.power_lower_w) & (actual_power <= self.power_upper_w)
        return {
            "joint_vi_coverage": float(within.all(axis=(1, 2)).mean()),
            "joint_power_coverage": float(power_within.all(axis=1).mean()),
            "mean_voltage_width_v": float((self.upper[..., 0] - self.lower[..., 0]).mean()),
            "mean_current_width_a": float((self.upper[..., 1] - self.lower[..., 1]).mean()),
            "mean_power_width_w": float((self.power_upper_w - self.power_lower_w).mean()),
        }


@dataclass(frozen=True)
class BlockConformalVI:
    """Maximum normalized residual over channels, horizons and each time block."""

    quantile: float
    scales: np.ndarray
    coverage: float
    block_size: int
    calibration_blocks: int
    calibration_samples: int
    discarded_tail_samples: int
    trained_through: pd.Timestamp
    calibrated_through: pd.Timestamp
    horizons: int

    def predict(self, predicted, *, origin_times) -> VIPredictionIntervals:
        """Apply frozen intervals after the last calibration target timestamp."""
        prediction = _vi(predicted, "predicted")
        times = _time_index(origin_times, name="origin_times")
        if len(times) != len(prediction) or prediction.shape[1] != self.horizons:
            raise ValueError("Prediction shape/time specification differs from calibration")
        if times[0] <= self.calibrated_through:
            raise ValueError("Evaluation origins must follow all calibration target labels")
        half_width = self.quantile * self.scales
        lower, upper = prediction - half_width, prediction + half_width
        if np.isinf(self.quantile):
            power_lower = np.full(prediction.shape[:2], -np.inf)
            power_upper = np.full(prediction.shape[:2], np.inf)
        else:
            products = np.stack(
                [
                    lower[..., 0] * lower[..., 1],
                    lower[..., 0] * upper[..., 1],
                    upper[..., 0] * lower[..., 1],
                    upper[..., 0] * upper[..., 1],
                ],
                axis=-1,
            )
            power_lower, power_upper = products.min(axis=-1), products.max(axis=-1)
        return VIPredictionIntervals(
            prediction,
            lower,
            upper,
            prediction[..., 0] * prediction[..., 1],
            power_lower,
            power_upper,
            self.coverage,
        )


def calibrate_block_conformal_vi(
    observed,
    predicted,
    *,
    origin_times,
    target_end_times,
    trained_through,
    scales,
    coverage: float = 0.9,
    block_size: int = 20,
) -> BlockConformalVI:
    """Calibrate joint multi-horizon V/I envelopes on a later time partition.

    ``scales`` is positive (V, A) or (horizon, 2), selected on training data or
    independently, never tuned on this calibration/evaluation block. Blocks are
    nonoverlapping consecutive forecast records. The incomplete trailing block
    is discarded from scores but its labels remain inside the embargo boundary.
    This row-block method is not a proof of temporal independence.
    """
    actual, prediction = _vi(observed, "observed"), _vi(predicted, "predicted")
    if actual.shape != prediction.shape:
        raise ValueError("Observed and predicted shapes must agree")
    origins = _time_index(origin_times, name="origin_times")
    ends = _time_index(target_end_times, name="target_end_times")
    trained = pd.Timestamp(trained_through)
    if not isinstance(trained, pd.Timestamp):
        raise ValueError("trained_through must be a valid timestamp")
    if len(origins) != len(actual) or len(ends) != len(actual):
        raise ValueError("Calibration clocks and observations must have equal lengths")
    if (ends < origins).any() or origins[0] <= trained:
        raise ValueError(
            "Calibration must follow training labels and targets cannot precede origins"
        )
    scale = np.asarray(scales, dtype=float)
    if (
        scale.shape not in {(2,), actual.shape[1:]}
        or not np.isfinite(scale).all()
        or (scale <= 0).any()
    ):
        raise ValueError("scales must be finite positive (V, A) or (horizon, 2)")
    if isinstance(block_size, bool) or not isinstance(block_size, int) or block_size < 1:
        raise ValueError("block_size must be a positive integer")
    blocks = len(actual) // block_size
    if not blocks:
        raise ValueError("Calibration must contain at least one complete block")
    residual = np.abs(actual - prediction) / scale
    sample_scores = residual.max(axis=(1, 2))
    block_scores = sample_scores[: blocks * block_size].reshape(blocks, block_size).max(axis=1)
    quantile = conformal_order_statistic(block_scores, coverage=coverage)
    return BlockConformalVI(
        quantile,
        scale.copy(),
        float(coverage),
        block_size,
        blocks,
        len(actual),
        len(actual) % block_size,
        trained,
        cast(pd.Timestamp, ends[-1]),
        actual.shape[1],
    )


__all__ = [
    "BlockConformalVI",
    "VIPredictionIntervals",
    "calibrate_block_conformal_vi",
    "conformal_order_statistic",
]
