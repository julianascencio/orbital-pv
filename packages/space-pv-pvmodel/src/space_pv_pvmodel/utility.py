"""Finite-horizon lunar power-service admission using existing EPS dispatch."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from space_pv_pvmodel.eps import BatterySpec, dispatch_power


def screen_power_service(
    time_s: ArrayLike,
    generation_w: ArrayLike,
    housekeeping_w: ArrayLike,
    customer_counts: list[int],
    *,
    customer_power_w: float,
    delivery_efficiency: float,
    battery: BatterySpec,
) -> pd.DataFrame:
    """Screen identical continuous customer loads over supplied intervals.

    Customer power is delivered at the customer; generation, housekeeping and
    battery limits are at the utility bus. The delivery loss applies only to
    customer power. Housekeeping may include externally modeled heater demand.

    Report both finite-horizon service and repeatable-profile feasibility. The
    latter additionally requires final SOC >= initial SOC; it is not a guarantee
    for another illumination profile. No load shedding, priority allocation,
    reliability probability, degradation or economic value is inferred.
    """
    if not customer_counts or any(
        isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in customer_counts
    ):
        raise ValueError("customer_counts must be nonempty nonnegative integers")
    if len(set(customer_counts)) != len(customer_counts):
        raise ValueError("customer_counts must be unique")
    if not np.isfinite(customer_power_w) or customer_power_w <= 0:
        raise ValueError("customer_power_w must be finite and positive")
    if not np.isfinite(delivery_efficiency) or not 0 < delivery_efficiency <= 1:
        raise ValueError("delivery_efficiency must lie in (0,1]")
    housekeeping = np.asarray(housekeeping_w, dtype=float)
    if not np.isfinite(housekeeping).all() or np.any(housekeeping < 0):
        raise ValueError("housekeeping_w must be finite and nonnegative")
    rows = []
    for count in customer_counts:
        customer_bus_w = count * customer_power_w / delivery_efficiency
        trace = dispatch_power(time_s, generation_w, housekeeping + customer_bus_w, battery=battery)
        unmet = float((trace.unserved_load_w * trace.duration_h).sum())
        final_soc = float(trace.soc_end.iloc[-1])
        no_shortfall = unmet <= 1e-6
        restored = final_soc >= battery.initial_soc - 1e-10
        rows.append(
            {
                "customers": count,
                "requested_customer_w": count * customer_power_w,
                "customer_bus_w": customer_bus_w,
                "unserved_bus_wh": unmet,
                "final_soc": final_soc,
                "minimum_soc": min(battery.initial_soc, float(trace.soc_end.min())),
                "finite_horizon_feasible": no_shortfall,
                "reserve_restored": restored,
                "repeatable_profile_feasible": no_shortfall and restored,
            }
        )
    return pd.DataFrame(rows)
