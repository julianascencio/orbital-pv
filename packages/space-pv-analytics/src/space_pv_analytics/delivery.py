"""Interval-exact delivered-power screening, without netting surplus against outages."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class DeliveryAssessment:
    """Finite-horizon metrics; energy in Wh, power in W, duration in hours.

    Availability is time at or above the target within a caller-declared watt
    tolerance. Shortfall energy is never reduced by that numerical tolerance.
    Backup ratings are ideal point-of-delivery requirements, not battery sizing.
    """

    duration_h: float
    delivered_wh: float
    required_wh: float
    served_wh: float
    shortfall_wh: float
    surplus_wh: float
    availability: float
    shortfall_h: float
    longest_shortfall_h: float
    backup_peak_w: float
    largest_event_shortfall_wh: float
    energy_target_met: bool


def delivery_chain(pv_dc_w: ArrayLike, efficiencies: dict[str, float]) -> pd.DataFrame:
    """Apply ordered scalar efficiencies to an interval PV DC power vector.

    Values are scenario assumptions unless calibrated externally. Beam capture,
    RF conversion and grid delivery must be separate entries supplied by the
    caller. This is accounting, not a beam/orbit/thermal propagation model.
    Each column is cumulative power after its named stage, in watts.
    """
    power = np.asarray(pv_dc_w, dtype=float)
    if power.ndim != 1 or not len(power) or not np.isfinite(power).all() or np.any(power < 0):
        raise ValueError("pv_dc_w must be a finite nonnegative vector")
    columns = {"pv_dc_w": power.copy()}
    if not efficiencies:
        raise ValueError("Supply at least one efficiency stage")
    for name, efficiency in efficiencies.items():
        if not isinstance(name, str) or not name.strip() or name == "pv_dc_w":
            raise ValueError("Stage names must be nonempty and not pv_dc_w")
        if not np.isfinite(efficiency) or not 0 <= efficiency <= 1:
            raise ValueError("Efficiencies must be finite fractions in [0, 1]")
        power = power * efficiency
        columns[name] = power.copy()
    return pd.DataFrame(columns)


def assess_delivery(
    time_edges_h: ArrayLike,
    delivered_w: ArrayLike,
    required_w: ArrayLike,
    *,
    energy_target_wh: float,
    tolerance_w: float = 0.0,
) -> DeliveryAssessment:
    """Screen piecewise-constant power over explicit contiguous interval edges.

    N+1 elapsed-hour boundaries describe N powers. Scalars broadcast. Missing
    values, duplicate/reversed edges and negative powers are rejected; no gap
    filling or implicit annualization. Energy target is for the supplied horizon.
    Event energy integrates each contiguous above-tolerance deficit event;
    tolerance affects availability/event classification only.
    """
    edges = np.asarray(time_edges_h, dtype=float)
    if (
        edges.ndim != 1
        or len(edges) < 2
        or not np.isfinite(edges).all()
        or np.any(np.diff(edges) <= 0)
    ):
        raise ValueError("time_edges_h must be finite and strictly increasing")
    duration = np.diff(edges)
    vectors = []
    for value in (delivered_w, required_w):
        a = np.asarray(value, dtype=float)
        if a.ndim == 0:
            a = np.full(len(duration), float(a))
        if a.shape != duration.shape or not np.isfinite(a).all() or np.any(a < 0):
            raise ValueError(
                "Power must be finite, nonnegative and scalar or one value per interval"
            )
        vectors.append(a)
    if (
        not np.isfinite([energy_target_wh, tolerance_w]).all()
        or min(energy_target_wh, tolerance_w) < 0
    ):
        raise ValueError("Energy target and tolerance must be finite and nonnegative")
    delivered, required = vectors
    deficit = np.maximum(required - delivered, 0)
    short = deficit > tolerance_w
    longest = largest = run_h = run_wh = 0.0
    for hours, loss, is_short in zip(duration, deficit, short, strict=True):
        if is_short:
            run_h += hours
            run_wh += hours * loss
            longest = max(longest, run_h)
            largest = max(largest, run_wh)
        else:
            run_h = run_wh = 0.0
    energy = float(delivered @ duration)
    total_h = float(duration.sum())
    short_h = float(duration[short].sum())
    return DeliveryAssessment(
        total_h,
        energy,
        float(required @ duration),
        float(np.minimum(delivered, required) @ duration),
        float(deficit @ duration),
        float(np.maximum(delivered - required, 0) @ duration),
        1 - short_h / total_h,
        short_h,
        float(longest),
        float(deficit.max()),
        float(largest),
        energy >= energy_target_wh,
    )
