"""Time-dependent rover energy routing on an explicitly discretized terrain."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class LunarRover:
    """Illustrative mobility/electrical inputs; no flight calibration implied."""

    mass_kg: float = 100.0
    rolling_resistance: float = 0.05
    drive_efficiency: float = 0.6
    speed_m_s: float = 0.1
    housekeeping_w: float = 20.0
    capacity_wh: float = 500.0
    initial_energy_wh: float = 400.0
    reserve_wh: float = 100.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    maximum_charge_w: float = 100.0
    maximum_discharge_w: float = 150.0
    maximum_slope_deg: float = 20.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.mass_kg <= 0 or self.speed_m_s <= 0 or self.capacity_wh <= 0:
            raise ValueError("Positive mass, speed and battery capacity required")
        for eta in (self.drive_efficiency, self.charge_efficiency, self.discharge_efficiency):
            if not 0 < eta <= 1:
                raise ValueError("Efficiencies must be in (0,1]")
        if not 0 <= self.reserve_wh <= self.initial_energy_wh <= self.capacity_wh:
            raise ValueError("Require 0 <= reserve <= initial energy <= capacity")
        if not 0 < self.maximum_slope_deg < 90:
            raise ValueError("Maximum slope must be in (0,90)")


def energy_aware_route(
    elevation_m: ArrayLike,
    time_s: ArrayLike,
    solar_power_w: ArrayLike,
    *,
    cell_size_m: float,
    start: tuple[int, int],
    goal: tuple[int, int],
    rover: LunarRover,
    heater_power_w: ArrayLike = 0.0,
) -> pd.DataFrame:
    """Find earliest feasible arrival; maximize remaining energy at equal arrival.

    Elevations are a local metric grid (row,column). NaNs mark impassable cells.
    Solar/heater cubes are (interval,row,column); scalar values broadcast.
    Moves use four neighbours or wait one entire time interval. A move requires
    speed*dt >= 3D edge length. Energy includes rolling resistance, uphill
    potential (g=1.62 m/s²), housekeeping and heaters, with no downhill recovery.

    Edge solar/heater power is the average of its endpoints for the full step;
    this explicitly approximates conditions during travel and any waiting. Each
    edge uses constant net power, so endpoint reserve checks also bound energy
    inside that interval. Charge/discharge limits and losses apply at the bus.
    Dominance pruning retains the greatest energy at each cell/time; no global
    continuous-space or continuous-time optimum is claimed. No wheel slip,
    boulders, radio visibility or terrain below grid resolution is modelled.
    """
    z, t = np.asarray(elevation_m, dtype=float), np.asarray(time_s, dtype=float)
    if z.ndim != 2 or min(z.shape) < 2 or np.isinf(z).any():
        raise ValueError("Require a 2D elevation grid; only NaN can mark obstacles")
    if t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError("Require increasing finite interval boundaries")
    if not np.isfinite(cell_size_m) or cell_size_m <= 0:
        raise ValueError("cell_size_m must be positive")
    for cell in (start, goal):
        if (
            len(cell) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, np.integer)) for v in cell)
            or not (0 <= cell[0] < z.shape[0] and 0 <= cell[1] < z.shape[1])
            or not np.isfinite(z[cell])
        ):
            raise ValueError("Start/goal must be valid grid cells")
    shape = (len(t) - 1, *z.shape)
    solar = np.broadcast_to(np.asarray(solar_power_w, dtype=float), shape)
    heater = np.broadcast_to(np.asarray(heater_power_w, dtype=float), shape)
    if (
        not np.isfinite(solar).all()
        or not np.isfinite(heater).all()
        or np.any(solar < 0)
        or np.any(heater < 0)
    ):
        raise ValueError("Solar and heater power must be finite and non-negative")
    energy = np.full(z.shape, -np.inf)
    energy[start] = rover.initial_energy_wh
    histories = [energy.copy()]
    predecessors = []
    arrival = 0 if start == goal else None
    for step, dt in enumerate(np.diff(t)):
        if arrival is not None:
            break
        next_energy = np.full(z.shape, -np.inf)
        parent = np.full((*z.shape, 2), -1, dtype=int)
        for row, col in np.argwhere(np.isfinite(energy)):
            for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                rr, cc = int(row + dr), int(col + dc)
                if not (0 <= rr < z.shape[0] and 0 <= cc < z.shape[1]) or not np.isfinite(
                    z[rr, cc]
                ):
                    continue
                dz = float(z[rr, cc] - z[row, col])
                moving = dr != 0 or dc != 0
                distance = float(np.hypot(cell_size_m, dz)) if moving else 0.0
                if distance > rover.speed_m_s * dt + 1e-9:
                    continue
                if (
                    moving
                    and np.rad2deg(np.arctan2(abs(dz), cell_size_m)) > rover.maximum_slope_deg
                ):
                    continue
                mechanical_j = (
                    rover.mass_kg
                    * 1.62
                    * (rover.rolling_resistance * distance + max(dz, 0))
                    / rover.drive_efficiency
                )
                demand = (
                    rover.housekeeping_w
                    + mechanical_j / dt
                    + (heater[step, row, col] + heater[step, rr, cc]) / 2
                )
                generation = (solar[step, row, col] + solar[step, rr, cc]) / 2
                net_w = generation - demand
                if -net_w > rover.maximum_discharge_w + 1e-9:
                    continue
                change_wh = (
                    (
                        min(net_w, rover.maximum_charge_w) * rover.charge_efficiency
                        if net_w >= 0
                        else net_w / rover.discharge_efficiency
                    )
                    * dt
                    / 3600
                )
                available = min(rover.capacity_wh, energy[row, col] + change_wh)
                if available >= rover.reserve_wh - 1e-9 and available > next_energy[rr, cc]:
                    next_energy[rr, cc] = available
                    parent[rr, cc] = [row, col]
        predecessors.append(parent)
        histories.append(next_energy.copy())
        energy = next_energy
        if np.isfinite(energy[goal]):
            arrival = step + 1
    if arrival is None:
        raise ValueError("No energy-feasible route within the supplied time window")
    cell = goal
    rows = []
    for step in range(arrival, -1, -1):
        rows.append(
            dict(
                time_s=float(t[step]),
                row=int(cell[0]),
                column=int(cell[1]),
                energy_wh=float(histories[step][cell]),
                elevation_m=float(z[cell]),
            )
        )
        if step:
            cell = tuple(predecessors[step - 1][cell])
    result = pd.DataFrame(rows[::-1])
    result.attrs.update(
        objective="earliest feasible arrival; most energy at equal time",
        grid_spacing_m=cell_size_m,
        model="4-neighbour time-expanded energy search; endpoint-averaged forcing",
    )
    return result
