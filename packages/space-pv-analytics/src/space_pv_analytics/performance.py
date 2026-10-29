from __future__ import annotations

import numpy as np
import pandas as pd

from space_pv_core.constants import DAYS_PER_YEAR
from space_pv_core.models import Case0Summary, DegradationEstimate

_REQUIRED = {"timestamp", "panel_id", "voltage_v", "current_a"}


def add_power(frame: pd.DataFrame) -> pd.DataFrame:
    missing = _REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out["power_w"] = out["voltage_v"].astype(float) * out["current_a"].astype(float)
    return out.sort_values(["panel_id", "timestamp"]).reset_index(drop=True)


def add_robust_baseline(frame: pd.DataFrame, *, reference_samples: int = 500) -> pd.DataFrame:
    """Add a telemetry-only upper-envelope normalization.

    Case 0 has no trusted Sun/eclipse/attitude state. Normalizing against a high
    reference quantile is intentionally safer than treating every low-power sample
    as a fault. Fault screening happens on daily upper-envelope health, not samples.
    """
    if "power_w" not in frame:
        frame = add_power(frame)

    pieces: list[pd.DataFrame] = []
    for _, panel in frame.groupby("panel_id", sort=False):
        panel = panel.copy()
        ref = panel.iloc[: min(reference_samples, len(panel))]["power_w"]
        reference = float(ref.quantile(0.95))
        if abs(reference) < 1e-12:
            reference = 1e-12
        panel["reference_power_w"] = reference
        panel["normalized_power"] = panel["power_w"] / reference
        pieces.append(panel)
    return pd.concat(pieces, ignore_index=True)


def daily_health(
    frame: pd.DataFrame,
    *,
    reference_samples: int = 500,
    anomaly_threshold: float = 5.0,
) -> pd.DataFrame:
    if "normalized_power" not in frame:
        frame = add_robust_baseline(frame, reference_samples=reference_samples)

    work = frame.copy()
    work["day"] = work["timestamp"].dt.floor("D")
    health = (
        work.groupby(["panel_id", "day"], as_index=False)
        .agg(
            power_envelope=("normalized_power", lambda s: float(s.quantile(0.95))),
            samples=("normalized_power", "size"),
        )
        .sort_values(["panel_id", "day"])
        .reset_index(drop=True)
    )

    pieces: list[pd.DataFrame] = []
    for _, panel in health.groupby("panel_id", sort=False):
        panel = panel.copy()
        n_ref = max(3, min(7, max(3, len(panel) // 5)))
        baseline = panel.iloc[:n_ref]["power_envelope"]
        center = float(baseline.median())
        mad = float((baseline - center).abs().median())
        scale = max(1.4826 * mad, 0.01)
        panel["health_residual"] = panel["power_envelope"] - center
        panel["robust_score"] = panel["health_residual"] / scale
        panel["is_anomaly"] = panel["robust_score"] <= -abs(anomaly_threshold)
        panel["baseline_envelope"] = center
        pieces.append(panel)
    return pd.concat(pieces, ignore_index=True)


def detect_persistent_loss(
    health: pd.DataFrame,
    *,
    loss_threshold: float = 0.15,
    persistence_days: int = 3,
) -> tuple[str | None, float | None]:
    if health.empty:
        return None, None
    aggregate = health.groupby("day", as_index=False)["power_envelope"].median().sort_values("day")
    n_ref = max(3, min(7, max(3, len(aggregate) // 5)))
    baseline = float(aggregate.iloc[:n_ref]["power_envelope"].median())
    if baseline <= 0:
        return None, None
    low = aggregate["power_envelope"] <= baseline * (1.0 - loss_threshold)
    run = low.rolling(persistence_days, min_periods=persistence_days).sum()
    hits = np.flatnonzero(run.to_numpy() >= persistence_days)
    if not len(hits):
        return None, None
    end_idx = int(hits[0])
    start_idx = end_idx - persistence_days + 1
    start = aggregate.iloc[start_idx]["day"]
    post = float(aggregate.iloc[start_idx:]["power_envelope"].median())
    loss = max(0.0, 1.0 - post / baseline)
    return pd.Timestamp(start).isoformat(), loss


def estimate_degradation(frame: pd.DataFrame) -> DegradationEstimate:
    health = daily_health(frame)
    aggregate = health.groupby("day", as_index=False)["power_envelope"].median().sort_values("day")
    loss_start, _ = detect_persistent_loss(health)
    if loss_start is not None:
        cutoff = pd.Timestamp(loss_start)
        stable = aggregate[aggregate["day"] < cutoff]
        if len(stable) >= 5:
            aggregate = stable

    if len(aggregate) < 2:
        y0 = float(aggregate["power_envelope"].iloc[0]) if len(aggregate) else 0.0
        return DegradationEstimate(0.0, 0.0, y0, len(aggregate))

    x = (aggregate["day"] - aggregate["day"].iloc[0]).dt.total_seconds().to_numpy() / 86_400.0
    y = aggregate["power_envelope"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return DegradationEstimate(float(slope), float(slope * DAYS_PER_YEAR * 100.0), float(intercept), len(aggregate))


def summarize_case0(frame: pd.DataFrame, *, anomaly_threshold: float = 5.0) -> Case0Summary:
    health = daily_health(frame, anomaly_threshold=anomaly_threshold)
    loss_start, loss_fraction = detect_persistent_loss(health)
    return Case0Summary(len(frame), int(frame["panel_id"].nunique()), float(health["is_anomaly"].mean()), estimate_degradation(frame), loss_start is not None, loss_start, loss_fraction)
