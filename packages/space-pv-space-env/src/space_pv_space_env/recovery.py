"""History-dependent, bounded reversible-loss scenario model."""

import numpy as np
import pandas as pd


def recovery_history(
    intervals: pd.DataFrame, *, initial_deficit: float = 0.0, permanent_retention: float = 1.0
) -> pd.DataFrame:
    """Integrate dD/dt = damage_rate*(1-D) - recovery_rate*D exactly per interval.

    Required columns: duration_h, damage_rate_h_inv, recovery_rate_h_inv.
    D is a dimensionless reversible power deficit in [0,1]. Supplied rates
    are nonnegative effective rates, NOT particle flux or universal material
    constants. Caller must calibrate them at matched temperature/illumination.
    Permanent retention is a fixed multiplicative factor; no dose conversion,
    thermal dynamics, heater cost or irreversible damage accumulation is modeled.
    Retention = permanent_retention*(1-D). Endpoints bound each constant-rate
    interval because the analytic solution is monotone within an interval.
    Mean retention is analytically integrated, not endpoint-averaged.
    """
    cols = ["duration_h", "damage_rate_h_inv", "recovery_rate_h_inv"]
    if intervals.empty or not set(cols).issubset(intervals.columns):
        raise ValueError("Nonempty history with duration and both rates required")
    a = intervals[cols].to_numpy(dtype=float)
    if not np.isfinite(a).all() or (a[:, 0] <= 0).any() or (a[:, 1:] < 0).any():
        raise ValueError("Finite positive durations and nonnegative rates required")
    if not np.isfinite([initial_deficit, permanent_retention]).all() or not (
        0 <= initial_deficit <= 1 and 0 <= permanent_retention <= 1
    ):
        raise ValueError("Initial deficit and permanent retention must be in [0,1]")
    deficit, elapsed, rows = initial_deficit, 0.0, []
    for duration, damage, recovery in a:
        total = damage + recovery
        if not np.isfinite(total) or not np.isfinite(total * duration):
            raise ValueError("Rate-duration product exceeds numerical range")
        start = deficit
        if total:
            equilibrium = damage / total
            x = total * duration
            decay = np.exp(-x)
            mean_decay = -np.expm1(-x) / x if x else 1.0
            deficit = equilibrium + (start - equilibrium) * decay
            mean_deficit = equilibrium + (start - equilibrium) * mean_decay
        else:
            mean_deficit = start
        elapsed += duration
        rows.append(
            {
                "end_h": elapsed,
                "start_retention": permanent_retention * (1 - start),
                "end_retention": permanent_retention * (1 - deficit),
                "mean_retention": permanent_retention * (1 - mean_deficit),
                "minimum_retention": permanent_retention * (1 - max(start, deficit)),
            }
        )
    return pd.concat([intervals.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
