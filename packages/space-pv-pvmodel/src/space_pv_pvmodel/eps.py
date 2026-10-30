"""Energy-conserving battery dispatch and bounded orbital workload studies.

Workload scheduling is a deterministic earliest-deadline heuristic, not an
optimal-control solver. Battery damage uses a user-calibrated Miner/rainflow
screening relation, not a chemistry-independent lifetime claim.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class BatterySpec:
    """Usable model parameters; limits are bus-side W, capacity is nominal Wh."""

    capacity_wh: float
    initial_soc: float = 0.8
    minimum_soc: float = 0.1
    maximum_soc: float = 0.95
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    max_charge_w: float = float("inf")
    max_discharge_w: float = float("inf")

    def __post_init__(self) -> None:
        if not np.isfinite(self.capacity_wh) or self.capacity_wh <= 0:
            raise ValueError("capacity_wh must be finite and positive")
        if not all(np.isfinite(x) for x in (self.minimum_soc, self.initial_soc, self.maximum_soc)):
            raise ValueError("SOC bounds must be finite")
        if not 0 <= self.minimum_soc <= self.initial_soc <= self.maximum_soc <= 1:
            raise ValueError("require 0 <= minimum_soc <= initial_soc <= maximum_soc <= 1")
        for efficiency in (self.charge_efficiency, self.discharge_efficiency):
            if not np.isfinite(efficiency) or not 0 < efficiency <= 1:
                raise ValueError("charge/discharge efficiencies must lie in (0, 1]")
        for limit in (self.max_charge_w, self.max_discharge_w):
            if np.isnan(limit) or limit < 0:
                raise ValueError("power limits must be non-negative")


def _interval_inputs(
    time_s: ArrayLike, *named_inputs: tuple[str, ArrayLike]
) -> tuple[np.ndarray, list[np.ndarray]]:
    times = np.asarray(time_s, dtype=float)
    if times.ndim != 1 or len(times) < 2 or not np.all(np.isfinite(times)):
        raise ValueError("time_s must contain finite interval boundaries")
    if np.any(np.diff(times) <= 0):
        raise ValueError("time_s must be strictly increasing")
    values = []
    for name, value in named_inputs:
        try:
            array = np.broadcast_to(np.asarray(value, dtype=float), (len(times) - 1,)).copy()
        except ValueError as exc:
            raise ValueError(f"{name} needs one value per interval or a scalar") from exc
        if not np.all(np.isfinite(array)) or np.any(array < 0):
            raise ValueError(f"{name} must be finite and non-negative")
        values.append(array)
    return times, values


def _dispatch_step(
    generation: float,
    requested: float,
    duration_h: float,
    soc: float,
    battery: BatterySpec,
    served_limit: float = float("inf"),
) -> dict[str, float]:
    target = min(requested, served_limit)
    charge = min(
        max(generation - target, 0.0),
        battery.max_charge_w,
        max(battery.maximum_soc - soc, 0.0)
        * battery.capacity_wh
        / (battery.charge_efficiency * duration_h),
    )
    discharge = min(
        max(target - generation, 0.0),
        battery.max_discharge_w,
        max(soc - battery.minimum_soc, 0.0)
        * battery.capacity_wh
        * battery.discharge_efficiency
        / duration_h,
    )
    served = min(generation, target) + discharge
    curtailed = max(generation - served - charge, 0.0)
    change = (
        charge * battery.charge_efficiency - discharge / battery.discharge_efficiency
    ) * duration_h
    next_soc = float(
        np.clip(soc + change / battery.capacity_wh, battery.minimum_soc, battery.maximum_soc)
    )
    return {
        "generation_w": generation,
        "requested_load_w": requested,
        "served_load_w": served,
        "unserved_load_w": max(requested - served, 0.0),
        "charge_w": charge,
        "discharge_w": discharge,
        "curtailed_w": curtailed,
        "soc_start": soc,
        "soc_end": next_soc,
        "stored_energy_change_wh": change,
        "battery_loss_wh": (
            charge * (1 - battery.charge_efficiency)
            + discharge * (1 / battery.discharge_efficiency - 1)
        )
        * duration_h,
        "power_balance_error_w": generation + discharge - served - charge - curtailed,
    }


def dispatch_power(
    time_s: ArrayLike,
    generation_w: ArrayLike,
    demand_w: ArrayLike,
    *,
    battery: BatterySpec,
    maximum_served_power_w: ArrayLike | None = None,
) -> pd.DataFrame:
    """Dispatch generation and storage across piecewise-constant time intervals.

    ``time_s`` contains N+1 interval boundaries; power arrays have N entries.
    Generation first supplies load, then charges storage; stored energy supplies
    deficits. Surplus is curtailed and unmet load is explicitly reported.
    ``maximum_served_power_w`` can enforce an externally calculated thermal cap.
    """
    times, values = _interval_inputs(time_s, ("generation_w", generation_w), ("demand_w", demand_w))
    generation, demand = values
    if maximum_served_power_w is None:
        limits = np.full(len(generation), np.inf)
    else:
        _, limit_values = _interval_inputs(
            time_s, ("maximum_served_power_w", maximum_served_power_w)
        )
        limits = limit_values[0]
    soc = battery.initial_soc
    rows = []
    for i, duration in enumerate(np.diff(times) / 3600):
        row = _dispatch_step(
            float(generation[i]), float(demand[i]), float(duration), soc, battery, float(limits[i])
        )
        row.update(interval_start_s=times[i], interval_end_s=times[i + 1], duration_h=duration)
        rows.append(row)
        soc = row["soc_end"]
    return pd.DataFrame(rows)


def rainflow_cycles(soc: ArrayLike) -> pd.DataFrame:
    """Count closed/full and residual/half SOC cycles with a stack algorithm.

    Consecutive identical samples are removed before extracting reversals.
    Columns are depth_of_discharge, mean_soc and count (0.5 or 1.0). Residual
    half cycles are retained; a constant trace therefore returns no cycles.
    """
    values = np.asarray(soc, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise ValueError("soc must be a nonempty finite one-dimensional trace")
    if np.any((values < 0) | (values > 1)):
        raise ValueError("SOC must lie in [0, 1]")
    values = values[np.r_[True, np.diff(values) != 0]]
    cycles: list[tuple[float, float, float]] = []
    if len(values) < 2:
        return pd.DataFrame(cycles, columns=["depth_of_discharge", "mean_soc", "count"])
    reversals = np.r_[
        values[0],
        values[1:-1][np.diff(values)[:-1] * np.diff(values)[1:] < 0],
        values[-1],
    ]
    stack: list[float] = []
    for point in reversals:
        stack.append(float(point))
        while len(stack) >= 3:
            earlier = abs(stack[-2] - stack[-3])
            later = abs(stack[-1] - stack[-2])
            if earlier > later:
                break
            mean = (stack[-2] + stack[-3]) / 2
            if len(stack) == 3:
                cycles.append((earlier, mean, 0.5))
                stack.pop(0)
            else:
                cycles.append((earlier, mean, 1.0))
                stack[-3:] = [stack[-1]]
    for left, right in pairwise(stack):
        cycles.append((abs(right - left), (right + left) / 2, 0.5))
    return pd.DataFrame(cycles, columns=["depth_of_discharge", "mean_soc", "count"])


def battery_cycle_damage(
    soc: ArrayLike,
    *,
    cycles_to_failure_at_full_depth: float,
    depth_exponent: float = 1.5,
) -> float:
    """Return cumulative Miner damage from a supplied cycle-depth calibration.

    One full-depth cycle contributes ``1 / cycles_to_failure_at_full_depth``.
    The result is a damage index, not a remaining-capacity percentage or a
    predicted failure date. Calendar aging, temperature and rate effects are
    not modeled. The calibration is intentionally required from the caller.
    """
    if not np.isfinite(cycles_to_failure_at_full_depth) or cycles_to_failure_at_full_depth <= 0:
        raise ValueError("cycles_to_failure_at_full_depth must be finite and positive")
    if not np.isfinite(depth_exponent) or depth_exponent <= 0:
        raise ValueError("depth_exponent must be finite and positive")
    cycles = rainflow_cycles(soc)
    return float(
        np.sum(cycles["count"] * cycles["depth_of_discharge"] ** depth_exponent)
        / cycles_to_failure_at_full_depth
    )


@dataclass(frozen=True)
class ComputeTask:
    """Deferrable compute energy with release/deadline aligned to interval edges."""

    energy_wh: float
    release_s: float
    deadline_s: float
    maximum_power_w: float

    def __post_init__(self) -> None:
        if not all(
            np.isfinite(x)
            for x in (self.energy_wh, self.release_s, self.deadline_s, self.maximum_power_w)
        ):
            raise ValueError("task parameters must be finite")
        if self.energy_wh < 0 or self.maximum_power_w <= 0 or self.deadline_s <= self.release_s:
            raise ValueError(
                "task needs nonnegative energy, positive power and deadline after release"
            )


def schedule_compute_workload(
    time_s: ArrayLike,
    generation_w: ArrayLike,
    base_load_w: ArrayLike,
    *,
    battery: BatterySpec,
    tasks: Sequence[ComputeTask],
    compute_power_limit_w: float,
    thermal_power_limit_w: ArrayLike | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Schedule tasks by earliest deadline, preferring current solar surplus.

    Each interval serves mandatory near-deadline work and otherwise uses solar
    surplus. Storage supports mandatory work subject to SOC/power limits. The
    deadline lookahead includes known global and interval thermal power caps.
    Per-task future capacity is an upper bound because tasks share resources;
    the heuristic still need not find every feasible multi-task schedule. The
    thermal cap applies to total served bus load; battery/converter heat and
    radiator transients need a separate thermal node. This deterministic
    heuristic does not guarantee the optimal feasible schedule.

    Returns dispatch telemetry and a per-task completion/unserved-energy table.
    """
    times, values = _interval_inputs(
        time_s, ("generation_w", generation_w), ("base_load_w", base_load_w)
    )
    generation, base = values
    if not np.isfinite(compute_power_limit_w) or compute_power_limit_w < 0:
        raise ValueError("compute_power_limit_w must be finite and non-negative")
    for task in tasks:
        if task.release_s not in times or task.deadline_s not in times:
            raise ValueError("task releases and deadlines must be aligned with time_s boundaries")
    if thermal_power_limit_w is None:
        thermal_limits = np.full(len(generation), np.inf)
    else:
        _, limit_values = _interval_inputs(time_s, ("thermal_power_limit_w", thermal_power_limit_w))
        thermal_limits = limit_values[0]
    remaining = np.asarray([task.energy_wh for task in tasks], dtype=float)
    completed = np.zeros(len(tasks))
    durations_h = np.diff(times) / 3600
    compute_capacities = np.minimum(compute_power_limit_w, np.maximum(thermal_limits - base, 0.0))
    # A task cannot defer work into future power capacity that the system will
    # not have. Keep each task's remaining hard-capacity integral and subtract
    # the current interval as time advances. This avoids a quadratic lookahead
    # inside the dispatch loop; it does not reserve shared capacity for tasks.
    future_capacity_wh = np.zeros(len(tasks))
    for j, task in enumerate(tasks):
        start = int(np.searchsorted(times, task.release_s))
        stop = int(np.searchsorted(times, task.deadline_s))
        future_capacity_wh[j] = np.sum(
            np.minimum(compute_capacities[start:stop], task.maximum_power_w)
            * durations_h[start:stop]
        )
    soc = battery.initial_soc
    rows = []
    for i, duration in enumerate(durations_h):
        active = sorted(
            (
                j
                for j, task in enumerate(tasks)
                if task.release_s <= times[i] < task.deadline_s and remaining[j] > 1e-12
            ),
            key=lambda j: (tasks[j].deadline_s, j),
        )
        capacity = float(compute_capacities[i])
        solar_surplus = max(generation[i] - base[i], 0.0)
        mandatory = 0.0
        for j in active:
            future_capacity_wh[j] = max(
                future_capacity_wh[j] - min(tasks[j].maximum_power_w, capacity) * duration,
                0.0,
            )
            mandatory += max(remaining[j] - future_capacity_wh[j], 0.0) / duration
        budget = min(capacity, max(solar_surplus, mandatory))
        allocated = np.zeros(len(tasks))
        for j in active:
            allocated[j] = min(tasks[j].maximum_power_w, remaining[j] / duration, budget)
            budget -= allocated[j]
        requested_compute = float(np.sum(allocated))
        row = _dispatch_step(
            float(generation[i]),
            float(base[i] + requested_compute),
            float(duration),
            soc,
            battery,
            float(thermal_limits[i]),
        )
        served_base = min(float(base[i]), row["served_load_w"])
        compute_available = max(row["served_load_w"] - served_base, 0.0)
        served_compute = 0.0
        for j in active:
            supplied = min(allocated[j], compute_available)
            completed[j] += supplied * duration
            remaining[j] = max(remaining[j] - supplied * duration, 0.0)
            compute_available -= supplied
            served_compute += supplied
        row.update(
            interval_start_s=times[i],
            interval_end_s=times[i + 1],
            duration_h=duration,
            base_load_w=base[i],
            served_base_w=served_base,
            compute_load_w=requested_compute,
            served_compute_w=served_compute,
        )
        rows.append(row)
        soc = row["soc_end"]
    task_table = pd.DataFrame(
        {
            "task": np.arange(len(tasks)),
            "requested_energy_wh": [task.energy_wh for task in tasks],
            "completed_energy_wh": completed,
            "unserved_energy_wh": remaining,
            "deadline_s": [task.deadline_s for task in tasks],
        }
    )
    return pd.DataFrame(rows), task_table


def radiator_feasibility(
    heat_load_w: float,
    *,
    area_m2: float,
    radiator_temperature_k: float,
    emissivity: float = 0.85,
    absorbed_environment_w_m2: float = 0.0,
    sink_temperature_k: float = 3.0,
) -> dict[str, float | bool]:
    """Evaluate a steady radiative heat-rejection bound for one effective area.

    ``absorbed_environment_w_m2`` already includes solar/albedo/IR absorption
    and view factors. No convection exists in this vacuum model. Required area
    is infinite if the environment prevents any positive net heat rejection.
    This does not guarantee chip-to-radiator heat transport or safe junction
    temperature, nor does it include radiator mass or puncture tolerance.
    """
    for name, value in (
        ("heat_load_w", heat_load_w),
        ("area_m2", area_m2),
        ("radiator_temperature_k", radiator_temperature_k),
        ("absorbed_environment_w_m2", absorbed_environment_w_m2),
        ("sink_temperature_k", sink_temperature_k),
    ):
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    if not np.isfinite(emissivity) or not 0 <= emissivity <= 1:
        raise ValueError("emissivity must lie in [0, 1]")
    flux = emissivity * 5.670374419e-8 * (radiator_temperature_k**4 - sink_temperature_k**4)
    flux -= absorbed_environment_w_m2
    capacity = area_m2 * flux
    required = heat_load_w / flux if flux > 0 else (0.0 if heat_load_w == 0 else float("inf"))
    return {
        "net_rejection_flux_w_m2": flux,
        "available_heat_rejection_w": max(capacity, 0.0),
        "required_area_m2": required,
        "thermal_margin_w": capacity - heat_load_w,
        "feasible": bool(capacity >= heat_load_w),
    }
