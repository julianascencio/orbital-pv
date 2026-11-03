"""Mars surface PV screening with explicit irradiance-model boundaries."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .model import PvwattsReference, pvwatts_dc_space


def dust_retention(sols: float | np.ndarray, *, loss_per_sol: float) -> np.ndarray:
    """Return (1-loss_per_sol)**sols; no cleaning events are assumed.

    Lorenz et al. (2020), doi:10.1029/2019EA000992, used 0.0028/sol for
    early InSight. It is a mission-specific scenario, not a global default.
    For cleaning events or measured histories, pass a dust-factor time series
    directly to ``mars_surface_power``.
    """
    sols = np.asarray(sols, dtype=float)
    if not np.all(np.isfinite(sols)) or np.any(sols < 0):
        raise ValueError("sols must be finite and nonnegative")
    if not np.isfinite(loss_per_sol) or not 0 <= loss_per_sol < 1:
        raise ValueError("loss_per_sol must be in [0, 1)")
    return np.power(1 - loss_per_sol, sols)


def mars_surface_power(
    local_true_solar_time_h: float | np.ndarray,
    *,
    latitude_deg: float,
    declination_deg: float | np.ndarray,
    sun_distance_au: float | np.ndarray,
    optical_depth: float | np.ndarray,
    reference: PvwattsReference,
    cell_temperature_c: float | np.ndarray,
    array_dust_factor: float | np.ndarray = 1.0,
    spectral_factor: float | np.ndarray = 1.0,
    atmosphere: str = "lorenz_horizontal",
    tilt_deg: float = 0.0,
    azimuth_deg: float = 180.0,
    diffuse_horizontal_w_m2: float | np.ndarray | None = None,
    ground_albedo: float = 0.0,
    solar_constant_w_m2: float = 1361.0,
) -> pd.DataFrame:
    """Calculate DC power at specified Mars local true solar times.

    ``lorenz_horizontal`` uses E0*cos(zenith)/(1+0.3*tau). The attenuation
    was published for normal-incidence cell response (Lorenz 2020, section 3);
    extending it over the day is an explicitly approximate horizontal-array
    model. Its output is an effective irradiance proxy, not measured broadband
    GHI. No tilted-array or diffuse separation is claimed in that mode.

    ``components`` uses Beer-Lambert direct beam, plane-parallel airmass,
    caller-supplied DHI and isotropic sky/ground transposition. DHI is required
    (explicit zero gives a direct-only calculation). Optical depth must be
    appropriate to the desired effective band; a 600-nm value is not a full
    spectral atmosphere. Flat terrain, no refraction/twilight/self-shadowing.
    Azimuth is clockwise from north. Temperatures are cell, not air, values.
    """
    if atmosphere not in {"lorenz_horizontal", "components"}:
        raise ValueError("atmosphere must be 'lorenz_horizontal' or 'components'")
    scalars = [latitude_deg, tilt_deg, azimuth_deg, ground_albedo, solar_constant_w_m2]
    if not np.all(np.isfinite(scalars)) or not -90 <= latitude_deg <= 90:
        raise ValueError("finite geometry and latitude in [-90, 90] required")
    if not 0 <= tilt_deg <= 90 or not 0 <= ground_albedo <= 1 or solar_constant_w_m2 <= 0:
        raise ValueError("tilt in [0, 90], albedo in [0, 1] and positive solar constant required")
    if atmosphere == "lorenz_horizontal":
        if tilt_deg != 0 or diffuse_horizontal_w_m2 is not None or ground_albedo != 0:
            raise ValueError("lorenz_horizontal requires a horizontal array and no DHI/albedo")
    elif diffuse_horizontal_w_m2 is None:
        raise ValueError(
            "components requires explicit diffuse_horizontal_w_m2; use 0 for direct-only"
        )
    values = np.broadcast_arrays(
        *[
            np.atleast_1d(np.asarray(v, dtype=float))
            for v in (
                local_true_solar_time_h,
                declination_deg,
                sun_distance_au,
                optical_depth,
                cell_temperature_c,
                array_dust_factor,
                spectral_factor,
                0.0 if diffuse_horizontal_w_m2 is None else diffuse_horizontal_w_m2,
            )
        ]
    )
    if any(v.ndim != 1 or not np.all(np.isfinite(v)) for v in values):
        raise ValueError("inputs must broadcast to finite one-dimensional arrays")
    ltst, dec, distance, tau, temperature, dust, spectrum, dhi = values
    if np.any((ltst < 0) | (ltst > 24)) or np.any(np.abs(dec) > 90):
        raise ValueError("LTST must be in [0, 24] and declination in [-90, 90]")
    if np.any(distance <= 0) or np.any(tau < 0) or np.any(temperature <= -273.15):
        raise ValueError(
            "distance must be positive, tau nonnegative and temperature above absolute zero"
        )
    if np.any((dust < 0) | (dust > 1)) or np.any(spectrum < 0) or np.any(dhi < 0):
        raise ValueError("dust factor must be in [0, 1]; spectrum and DHI nonnegative")
    if atmosphere == "lorenz_horizontal" and np.any(tau > 5):
        raise ValueError("Lorenz approximation is unsupported above optical depth 5")
    ref_values = [
        reference.pdc0_w,
        reference.gamma_pdc_per_c,
        reference.reference_irradiance_w_m2,
        reference.reference_temperature_c,
    ]
    if (
        not np.all(np.isfinite(ref_values))
        or reference.pdc0_w <= 0
        or reference.reference_irradiance_w_m2 <= 0
    ):
        raise ValueError("reference must be finite with positive power and irradiance")
    if np.any(
        1 + reference.gamma_pdc_per_c * (temperature - reference.reference_temperature_c) < 0
    ):
        raise ValueError("temperature correction would produce negative power")
    phi, delta = np.deg2rad(latitude_deg), np.deg2rad(dec)
    hour = np.deg2rad((ltst - 12) * 15)
    east = -np.cos(delta) * np.sin(hour)
    north = np.cos(phi) * np.sin(delta) - np.sin(phi) * np.cos(delta) * np.cos(hour)
    up = np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.cos(hour)
    daylight = up > 1e-12
    mu = np.where(daylight, up, 0.0)
    top = solar_constant_w_m2 / distance**2
    result = pd.DataFrame(
        {
            "ltst_h": ltst,
            "cosine_zenith": mu,
            "toa_normal_w_m2": top,
            "optical_depth": tau,
            "array_dust_factor": dust,
            "cell_temperature_c": temperature,
        }
    )
    if atmosphere == "lorenz_horizontal":
        irradiance = top * mu / (1 + 0.3 * tau)
        result["horizontal_effective_proxy_w_m2"] = irradiance
    else:
        beta, azimuth = np.deg2rad(tilt_deg), np.deg2rad(azimuth_deg)
        cosine = np.maximum(
            0,
            east * np.sin(beta) * np.sin(azimuth)
            + north * np.sin(beta) * np.cos(azimuth)
            + up * np.cos(beta),
        )
        dni = np.where(daylight, top * np.exp(-tau / np.maximum(mu, 1e-12)), 0.0)
        if np.any((~daylight) & (dhi > 0)):
            raise ValueError("DHI must be zero at night; twilight is outside this model")
        ghi = dni * mu + dhi
        irradiance = (
            dni * cosine
            + dhi * (1 + np.cos(beta)) / 2
            + ghi * ground_albedo * (1 - np.cos(beta)) / 2
        )
        result["dni_w_m2"], result["dhi_w_m2"] = dni, dhi
        result["ghi_w_m2"], result["poa_w_m2"] = ghi, irradiance
    effective = irradiance * dust * spectrum
    result["effective_irradiance_w_m2"] = effective
    result["dc_power_w"] = pvwatts_dc_space(effective, temperature, reference)
    result.attrs.update(
        atmosphere=atmosphere,
        power_boundary="array DC before battery/EPS losses",
        irradiance_kind="effective proxy"
        if atmosphere == "lorenz_horizontal"
        else "provided-DHI components",
    )
    return result
