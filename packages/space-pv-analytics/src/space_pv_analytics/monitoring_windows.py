"""Deterministic monitoring windows from explicitly bounded arrival forecasts."""

import numpy as np
import pandas as pd


def _utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("Timestamps must be valid and explicitly timezone-aware")
    return stamp.tz_convert("UTC")


def forecast_monitoring_windows(
    forecasts: pd.DataFrame, *, as_of_utc: str, missing_bound_hours: float | None = None
):
    """Return disjoint future windows and the eligible input forecast bounds.

    Required columns: method, submitted_utc, arrival_utc, before_hours,
    after_hours. Supply one version per method for ONE event; aggregate/ensemble
    rows must be removed by the caller. Future submissions are excluded to avoid
    lookahead. Missing bounds require an explicit symmetric planning assumption,
    never silently zero uncertainty. Bounds are NOT confidence intervals.
    Union windows preserve gaps, merge touching intervals, and clip at as_of.
    No storm probability, PV degradation or operational recommendation is inferred.
    """
    required = {"method", "submitted_utc", "arrival_utc", "before_hours", "after_hours"}
    if not required.issubset(forecasts.columns) or forecasts.empty:
        raise ValueError("Nonempty forecasts with required columns needed")
    cutoff = _utc(as_of_utc)
    if missing_bound_hours is not None and (
        not np.isfinite(missing_bound_hours) or missing_bound_hours <= 0
    ):
        raise ValueError("Missing-bound policy must be finite and positive")
    data = forecasts.copy()
    data["submitted_utc"] = data.submitted_utc.map(_utc)
    data = data[data.submitted_utc <= cutoff].copy()
    if data.empty or data.method.isna().any() or data.method.duplicated().any():
        raise ValueError("Need eligible forecasts with unique nonmissing methods")
    data["arrival_utc"] = data.arrival_utc.map(_utc)
    data["assumed_bound"] = data[["before_hours", "after_hours"]].isna().any(axis=1)
    for col in ("before_hours", "after_hours"):
        values = pd.to_numeric(data[col], errors="raise")
        if values.isna().any():
            if missing_bound_hours is None:
                raise ValueError("Missing bounds require an explicit policy")
            values = values.fillna(missing_bound_hours)
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("Bounds must be finite and nonnegative hours")
        data[col] = values
    data["start_utc"] = data.arrival_utc - pd.to_timedelta(data.before_hours, unit="h")
    data["end_utc"] = data.arrival_utc + pd.to_timedelta(data.after_hours, unit="h")
    merged = []
    for row in data.sort_values("start_utc").itertuples():
        start, end = max(row.start_utc, cutoff), row.end_utc
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return pd.DataFrame(merged, columns=["start_utc", "end_utc"]), data


def monitoring_sample_budget(windows: pd.DataFrame, *, cadence_s: float, bytes_per_sample: int):
    """Budget samples at each interval start then every cadence, excluding end.

    Require sorted, disjoint intervals. No compression/protocol overhead assumed.
    Counts restart per window, so partial final cadences still require a sample.
    """
    if not np.isfinite(cadence_s) or cadence_s <= 0:
        raise ValueError("cadence_s must be finite and positive")
    if (
        isinstance(bytes_per_sample, bool)
        or not isinstance(bytes_per_sample, int)
        or bytes_per_sample <= 0
    ):
        raise ValueError("bytes_per_sample must be a positive integer")
    total_s, samples, previous = 0.0, 0, None
    for start_value, end_value in windows[["start_utc", "end_utc"]].itertuples(
        index=False, name=None
    ):
        start, end = _utc(start_value), _utc(end_value)
        if end <= start or (previous is not None and start < previous):
            raise ValueError("Windows must be positive, sorted and disjoint")
        duration = (end - start).total_seconds()
        total_s += duration
        samples += int(np.ceil(duration / cadence_s))
        previous = end
    return {
        "monitoring_hours": total_s / 3600,
        "samples": samples,
        "bytes": samples * bytes_per_sample,
    }
