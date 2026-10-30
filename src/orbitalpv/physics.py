"""Public research physics API: thermal, radiation, spectral, circuits and EPS.

These models are scientific screening tools with explicit approximations. They
are not flight-qualified designs or exact reproductions of the cited papers.
"""

from space_pv_pvmodel.eps import (
    BatterySpec,
    ComputeTask,
    battery_cycle_damage,
    dispatch_power,
    radiator_feasibility,
    rainflow_cycles,
    schedule_compute_workload,
)
from space_pv_pvmodel.spectral import (
    TandemCurrent,
    spectral_photocurrent_density,
    tandem_current_density,
)
from space_pv_pvmodel.topology import PVSubstring, array_iv_curve
from space_pv_space_env.radiation import (
    RadiationExposure,
    RadiationResponse,
    radiation_equivalent_fluence,
    retained_power_fraction,
)
from space_pv_space_env.thermal import ThermalSurface, simulate_panel_thermal

__all__ = [
    "BatterySpec",
    "ComputeTask",
    "PVSubstring",
    "RadiationExposure",
    "RadiationResponse",
    "TandemCurrent",
    "ThermalSurface",
    "array_iv_curve",
    "battery_cycle_damage",
    "dispatch_power",
    "radiation_equivalent_fluence",
    "radiator_feasibility",
    "rainflow_cycles",
    "retained_power_fraction",
    "schedule_compute_workload",
    "simulate_panel_thermal",
    "spectral_photocurrent_density",
    "tandem_current_density",
]
