"""Exact small-instance scheduling of noninterruptible charging sessions."""

from itertools import product
from math import prod

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike


def schedule_charging(
    generation_w: ArrayLike,
    base_load_w: ArrayLike,
    requests: pd.DataFrame,
    *,
    slot_hours: float,
    efficiency: float,
    max_combinations: int = 100_000,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Minimize peak bus deficit, then deficit energy, then total bus peak.

    Exhaustively enumerate integer-slot starts for constant-power, contiguous
    sessions. Requests require unique id, release_slot, deadline_slot (exclusive),
    duration_slots and delivered_power_w. All jobs must fit their windows.
    Delivery efficiency converts receiver power to tower-bus demand. Tie breaking
    is earliest starts in input order. Optimality applies ONLY to the supplied
    discrete grid and objective, not battery SOC or converter thermal limits.
    No battery or physical charging taper is modeled here; evaluate returned
    loads with a separate dispatch model. Reject oversized search spaces before
    enumeration. Inputs are deterministic forecasts, not reliability evidence.
    """
    generation = np.asarray(generation_w, dtype=float)
    base = np.asarray(base_load_w, dtype=float)
    if generation.ndim != 1 or not generation.size or base.shape != generation.shape:
        raise ValueError("Require nonempty, equally sized 1-D generation and base arrays")
    if not np.isfinite([generation, base]).all() or np.any(generation < 0) or np.any(base < 0):
        raise ValueError("Power must be finite and nonnegative")
    if (
        not np.isfinite([slot_hours, efficiency]).all()
        or slot_hours <= 0
        or not 0 < efficiency <= 1
    ):
        raise ValueError("Require positive slot_hours and efficiency in (0,1]")
    if (
        isinstance(max_combinations, bool)
        or not isinstance(max_combinations, int)
        or max_combinations < 1
    ):
        raise ValueError("max_combinations must be a positive integer")
    required = {"id", "release_slot", "deadline_slot", "duration_slots", "delivered_power_w"}
    if not required.issubset(requests.columns) or requests.empty:
        raise ValueError("Nonempty requests with all required columns needed")
    if requests.id.isna().any() or requests.id.duplicated().any():
        raise ValueError("Request IDs must be unique and nonmissing")
    windows, jobs = [], []
    for row in requests.to_dict("records"):
        indices = [row[k] for k in ("release_slot", "deadline_slot", "duration_slots")]
        if any(isinstance(x, bool) or not isinstance(x, (int, np.integer)) for x in indices):
            raise ValueError("Window and duration values must be integer slots")
        release, deadline, duration = indices
        power = float(row["delivered_power_w"])
        if (
            not 0 <= release < deadline <= len(generation)
            or not 1 <= duration <= deadline - release
        ):
            raise ValueError("Each session must fit its window within the horizon")
        if not np.isfinite(power) or power <= 0:
            raise ValueError("Delivered power must be finite and positive")
        windows.append(range(release, deadline - duration + 1))
        jobs.append((duration, power / efficiency))
    if prod(map(len, windows)) > max_combinations:
        raise ValueError("Search exceeds max_combinations; coarsen grid or reduce jobs")
    best_score, best_starts, best_load = None, None, None
    for starts in product(*windows):
        load = base.copy()
        for start, (duration, power) in zip(starts, jobs, strict=True):
            load[start : start + duration] += power
        deficit = np.maximum(load - generation, 0)
        score = (float(deficit.max()), float(deficit.sum()), float(load.max()))
        if best_score is None or score < best_score:
            best_score, best_starts, best_load = score, starts, load
    assert best_load is not None and best_starts is not None
    schedule = requests.copy()
    schedule["start_slot"] = best_starts
    schedule["end_slot"] = schedule.start_slot + schedule.duration_slots
    schedule["delivered_energy_wh"] = (
        schedule.delivered_power_w * schedule.duration_slots * slot_hours
    )
    trace = pd.DataFrame(
        {
            "slot": np.arange(len(generation)),
            "generation_w": generation,
            "base_load_w": base,
            "load_w": best_load,
            "deficit_w": np.maximum(best_load - generation, 0),
        }
    )
    return schedule, trace
