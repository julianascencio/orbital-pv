"""Mars surface PV, mission data and reproducible daily screening models."""

from __future__ import annotations

import numpy as np
import pandas as pd

from space_pv_connectors.mars import (
    InSightOpacityConnector,
    InSightSolarConnector,
    parse_insight_currents,
    parse_insight_energy,
    parse_insight_opacity,
)
from space_pv_pvmodel.mars import dust_retention, mars_surface_power
from space_pv_pvmodel.model import PvwattsReference
from space_pv_space_env.mars import MARS_SOL_SECONDS, mars_declination, mars_solar_parameters


def simulate_mars_sol(
    *,
    julian_date_tt: float,
    latitude_deg: float,
    reference: PvwattsReference,
    optical_depth: float,
    cell_temperature_c: float | np.ndarray,
    array_dust_factor: float = 1.0,
    spectral_factor: float = 1.0,
    atmosphere: str = "lorenz_horizontal",
    tilt_deg: float = 0.0,
    azimuth_deg: float = 180.0,
    diffuse_horizontal_w_m2: float | np.ndarray | None = None,
    ground_albedo: float = 0.0,
    samples: int = 289,
) -> pd.DataFrame:
    """Simulate a full sol and integrate DC energy in Earth watt-hours.

    Freeze seasonal geometry at the supplied representative TT date. Sample
    LTST 0..24 including both endpoints; elapsed SI seconds span one mean sol
    (88775.244 s). This neglects small within-sol seasonal/EOT changes. If
    supplying temperature or DHI vectors, their length must equal ``samples``.
    ``energy_wh`` in frame attrs is array DC, before conversion/storage losses.
    """
    if np.ndim(julian_date_tt) != 0:
        raise ValueError("julian_date_tt must be scalar")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 25:
        raise ValueError("samples must be an integer >= 25")
    geometry = mars_solar_parameters(julian_date_tt)
    frame = mars_surface_power(
        np.linspace(0, 24, samples),
        latitude_deg=latitude_deg,
        declination_deg=geometry["declination_deg"],
        sun_distance_au=geometry["sun_distance_au"],
        optical_depth=optical_depth,
        reference=reference,
        cell_temperature_c=cell_temperature_c,
        array_dust_factor=array_dust_factor,
        spectral_factor=spectral_factor,
        atmosphere=atmosphere,
        tilt_deg=tilt_deg,
        azimuth_deg=azimuth_deg,
        diffuse_horizontal_w_m2=diffuse_horizontal_w_m2,
        ground_albedo=ground_albedo,
    )
    frame["elapsed_seconds"] = np.linspace(0, MARS_SOL_SECONDS, samples)
    frame.attrs.update({k: float(v) for k, v in geometry.items()})
    frame.attrs["energy_wh"] = float(np.trapezoid(frame.dc_power_w, frame.elapsed_seconds) / 3600)
    frame.attrs["time_basis"] = "LTST; frozen season; one mean sol in SI seconds"
    return frame


__all__ = [
    "MARS_SOL_SECONDS",
    "InSightOpacityConnector",
    "InSightSolarConnector",
    "dust_retention",
    "mars_declination",
    "mars_solar_parameters",
    "mars_surface_power",
    "parse_insight_currents",
    "parse_insight_energy",
    "parse_insight_opacity",
    "simulate_mars_sol",
]
