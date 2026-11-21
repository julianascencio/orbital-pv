"""Backward battery reserve envelope for a prescribed power profile."""

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from space_pv_pvmodel.eps import BatterySpec, _interval_inputs


class InfeasibleReserveError(ValueError):
    """No allowed initial SOC can supply the complete requested profile."""


def battery_reserve_envelope(
    time_s: ArrayLike,
    generation_w: ArrayLike,
    demand_w: ArrayLike,
    *,
    battery: BatterySpec,
    terminal_soc: float,
) -> pd.DataFrame:
    """Minimum stored energy at each boundary to serve the remaining profile.

    Uses the same piecewise-constant, bus-side W and nominal Wh conventions as
    ``dispatch_power``. Work backward from ``terminal_soc``. During a deficit,
    add deficit Wh / discharge efficiency; during surplus, subtract the
    charge-limited surplus Wh * charge efficiency, bounded below by minimum
    SOC. Capacity overflow or insufficient discharge power makes the requested
    profile impossible for *any* initial SOC and raises InfeasibleReserveError.

    The returned N+1 rows contain time_s, required_energy_wh, required_soc.
    Compare its first required_soc with battery.initial_soc; that initial value
    does not affect the calculation. Equality is sufficient under this model.
    This is an exact finite-profile bound, not a forecast or flight guarantee.
    No self-discharge, thermal dynamics, voltage or attitude dynamics are modeled.
    """
    times, values = _interval_inputs(time_s, ("generation_w", generation_w), ("demand_w", demand_w))
    generation, demand = values
    if (
        not np.isfinite(terminal_soc)
        or not battery.minimum_soc <= terminal_soc <= battery.maximum_soc
    ):
        raise ValueError("terminal_soc must lie within battery SOC bounds")
    lower = battery.minimum_soc * battery.capacity_wh
    upper = battery.maximum_soc * battery.capacity_wh
    required = np.empty(len(times))
    required[-1] = terminal_soc * battery.capacity_wh
    for i in range(len(times) - 2, -1, -1):
        duration_h = (times[i + 1] - times[i]) / 3600
        net = generation[i] - demand[i]
        if net < 0:
            if -net > battery.max_discharge_w:
                raise InfeasibleReserveError(f"Discharge power limit exceeded in interval {i}")
            required[i] = required[i + 1] - net * duration_h / battery.discharge_efficiency
        else:
            gain = min(net, battery.max_charge_w) * duration_h * battery.charge_efficiency
            required[i] = max(lower, required[i + 1] - gain)
        if required[i] > upper + 1e-10 * battery.capacity_wh:
            raise InfeasibleReserveError(f"Storage capacity exceeded at boundary {i}")
        required[i] = min(required[i], upper)
    return pd.DataFrame(
        {
            "time_s": times,
            "required_energy_wh": required,
            "required_soc": required / battery.capacity_wh,
        }
    )
