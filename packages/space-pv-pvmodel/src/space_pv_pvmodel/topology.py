"""Array I-V composition with idealized bypass diodes and fault scenarios.

The generating branch is an ideal single-diode characteristic with optional
series resistance and no shunt leakage. Parallel strings have blocking diodes
idealized as zero voltage drop, so reverse current into weak strings is excluded.
This is a bounded circuit-screening model, not an arcing or hot-spot simulation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class PVSubstring:
    """Equivalent generating substring and its bypass branch.

    ``diode_voltage_v`` is n*N_s*k*T/q. Photocurrent is not exact short-circuit
    current when a nonzero series resistance is supplied. An ``open`` fault
    opens the generating branch; a present bypass diode can still carry current.
    Set ``bypass_voltage_v=None`` for an unbypassed open circuit. A ``short``
    faults the entire substring to zero voltage.
    """

    photocurrent_a: float
    open_circuit_voltage_v: float
    diode_voltage_v: float = 0.6
    series_resistance_ohm: float = 0.0
    bypass_voltage_v: float | None = 0.5
    fault: Literal["healthy", "open", "short"] = "healthy"

    def __post_init__(self) -> None:
        for name in ("photocurrent_a", "open_circuit_voltage_v", "series_resistance_ohm"):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not np.isfinite(self.diode_voltage_v) or self.diode_voltage_v <= 0:
            raise ValueError("diode_voltage_v must be finite and positive")
        if self.open_circuit_voltage_v / self.diode_voltage_v > 700:
            raise ValueError("open-circuit to diode voltage ratio is numerically unsupported")
        if self.photocurrent_a > 0 and self.open_circuit_voltage_v == 0:
            raise ValueError("a generating substring needs a positive open-circuit voltage")
        if self.photocurrent_a == 0 and self.open_circuit_voltage_v != 0:
            raise ValueError("a dark substring must have zero open-circuit voltage")
        if self.bypass_voltage_v is not None and (
            not np.isfinite(self.bypass_voltage_v) or self.bypass_voltage_v < 0
        ):
            raise ValueError("bypass_voltage_v must be non-negative or None")
        if self.fault not in {"healthy", "open", "short"}:
            raise ValueError("fault must be healthy, open, or short")


def _substring_voltage(component: PVSubstring, current: np.ndarray) -> np.ndarray:
    if component.fault == "short":
        return np.zeros_like(current)
    if component.fault == "open" or component.photocurrent_a == 0:
        voltage = np.where(current > 0, -np.inf, 0.0)
    else:
        saturation = component.photocurrent_a / np.expm1(
            component.open_circuit_voltage_v / component.diode_voltage_v
        )
        diode_argument = (component.photocurrent_a + saturation - current) / saturation
        with np.errstate(divide="ignore", invalid="ignore"):
            voltage = component.diode_voltage_v * np.log(np.maximum(diode_argument, 0.0))
        voltage -= current * component.series_resistance_ohm
    if component.bypass_voltage_v is not None:
        voltage = np.maximum(voltage, -component.bypass_voltage_v)
    return voltage


def array_iv_curve(
    strings: Sequence[Sequence[PVSubstring]],
    voltage_v: ArrayLike | None = None,
    *,
    points: int = 501,
) -> pd.DataFrame:
    """Compose series substrings and parallel strings on a common voltage grid.

    Nonnegative voltage/current represent the generating quadrant. Bypass
    conduction is a constant voltage-drop approximation. Current is obtained
    by monotone bisection of each string's voltage-at-current relation. MPP
    attributes describe the sampled grid, so refine it for an accurate MPP.
    """
    circuits = [list(string) for string in strings]
    if not circuits or any(not string for string in circuits):
        raise ValueError("provide at least one nonempty string")
    if any(not isinstance(cell, PVSubstring) for string in circuits for cell in string):
        raise TypeError("strings must contain PVSubstring objects")
    open_voltages = [
        sum(cell.open_circuit_voltage_v for cell in string if cell.fault == "healthy")
        for string in circuits
    ]
    if voltage_v is None:
        if isinstance(points, bool) or int(points) != points or points < 2:
            raise ValueError("points must be an integer of at least two")
        voltage = np.linspace(0.0, max(max(open_voltages), 1.0), int(points))
    else:
        voltage = np.asarray(voltage_v, dtype=float)
        if voltage.ndim != 1 or len(voltage) < 2:
            raise ValueError("voltage_v must have at least two points")
        if not np.all(np.isfinite(voltage)) or np.any(voltage < 0):
            raise ValueError("voltage_v must be finite and non-negative")
        if np.any(np.diff(voltage) <= 0):
            raise ValueError("voltage_v must be strictly increasing")
    string_currents = []
    for string, open_voltage in zip(circuits, open_voltages, strict=True):
        broken = any(cell.fault == "open" and cell.bypass_voltage_v is None for cell in string)
        max_current = (
            max(cell.photocurrent_a for cell in string if cell.fault != "short")
            if any(cell.fault != "short" for cell in string)
            else 0.0
        )
        if broken or max_current == 0 or open_voltage == 0:
            string_currents.append(np.zeros_like(voltage))
            continue
        low = np.zeros_like(voltage)
        high = np.full_like(voltage, max_current * (1 + 1e-10))
        for _ in range(80):
            midpoint = (low + high) / 2
            available_voltage = sum(_substring_voltage(cell, midpoint) for cell in string)
            can_supply = available_voltage > voltage
            low = np.where(can_supply, midpoint, low)
            high = np.where(can_supply, high, midpoint)
        current = np.where(voltage >= open_voltage, 0.0, (low + high) / 2)
        string_currents.append(current)
    total_current = np.sum(string_currents, axis=0)
    result = pd.DataFrame({"voltage_v": voltage, "current_a": total_current})
    result["power_w"] = voltage * total_current
    for index, current in enumerate(string_currents):
        result[f"string_{index}_current_a"] = current
    optimum = int(np.argmax(result["power_w"].to_numpy()))
    result.attrs.update(
        pmp_w=float(result["power_w"].iloc[optimum]),
        vmp_v=float(voltage[optimum]),
        imp_a=float(total_current[optimum]),
        model="ideal diode, series resistance, constant-drop bypass, ideal string blocking",
    )
    return result
