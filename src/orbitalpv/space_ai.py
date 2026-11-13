"""Screening methods inspired by arXiv:2511.19468v2, not a flight design.

SI units unless indicated. Optical far-field and near-field geometry are
separate. Radiation dose extrapolations are conditional on the tested device,
workload, shielding and spectrum; they are not generic space qualification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from math import expm1, log2, pi
from pathlib import Path

import numpy as np
import pandas as pd

from .orbit import circular_orbit_period_s

LIGHT_SPEED_M_S = 299_792_458.0
PLANCK_J_S = 6.62607015e-34
SECONDS_PER_YEAR = 365.25 * 86400


def _positive(name: str, value: float, *, zero: bool = False) -> None:
    if not np.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")


def _integer(name: str, value: int, lower: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower:
        raise ValueError(f"{name} must be an integer >= {lower}")


@dataclass(frozen=True)
class OpticalLinkSpec:
    """One-direction total power across DWDM channels in one aperture.

    ``channel_rate_gbps`` is explicitly per direction. It must not be inferred
    by doubling a source's ambiguous 'bidirectional' figure. Aperture efficiency
    applies separately at transmitter and receiver; loss_db is nonnegative.
    """

    transmit_power_w: float = 5.0
    aperture_diameter_m: float = 0.1
    wavelength_m: float = 1.55e-6
    aperture_efficiency: float = 0.8
    loss_db: float = 3.0
    photons_per_bit: float = 195.6
    channels: int = 24
    channel_rate_gbps: float = 400.0
    receiver_threshold_dbm_per_channel: float = -20.0

    def __post_init__(self) -> None:
        for name in (
            "transmit_power_w",
            "aperture_diameter_m",
            "wavelength_m",
            "photons_per_bit",
            "channel_rate_gbps",
        ):
            _positive(name, getattr(self, name))
        _positive("loss_db", self.loss_db, zero=True)
        if not np.isfinite(self.aperture_efficiency) or not 0 < self.aperture_efficiency <= 1:
            raise ValueError("aperture_efficiency must lie in (0, 1]")
        if not np.isfinite(self.receiver_threshold_dbm_per_channel):
            raise ValueError("receiver threshold must be finite")
        _integer("channels", self.channels)


def optical_link_budget(distance_m, spec: OpticalLinkSpec | None = None) -> pd.DataFrame:
    """Eq. 1 Friis power, photon ceiling and equal-channel receiver margin.

    Reject distances below 2 D²/lambda, a conservative far-field boundary.
    ``screened_rate_gbps`` is a ceiling, not measured payload throughput. The
    full-rate receiver threshold is an additional feasibility condition; a
    negative margin does not establish operation at a reduced modulation rate.
    Pointing/beam quality must be included in the supplied loss allowance.
    """
    spec = OpticalLinkSpec() if spec is None else spec
    distance = np.atleast_1d(np.asarray(distance_m, dtype=float))
    boundary = 2 * spec.aperture_diameter_m**2 / spec.wavelength_m
    if (
        distance.ndim != 1
        or distance.size == 0
        or np.any(~np.isfinite(distance))
        or np.any(distance < boundary)
    ):
        raise ValueError(
            f"Distances must be a nonempty finite vector >= far-field boundary {boundary:g} m"
        )
    gain = spec.aperture_efficiency * (pi * spec.aperture_diameter_m / spec.wavelength_m) ** 2
    received = (
        spec.transmit_power_w
        * gain**2
        * (spec.wavelength_m / (4 * pi * distance)) ** 2
        * 10 ** (-spec.loss_db / 10)
    )
    photon_rate = (
        received / (PLANCK_J_S * LIGHT_SPEED_M_S / spec.wavelength_m) / spec.photons_per_bit / 1e9
    )
    electronics_rate = spec.channels * spec.channel_rate_gbps
    margin = (
        10 * np.log10(received / spec.channels / 1e-3) - spec.receiver_threshold_dbm_per_channel
    )
    return pd.DataFrame(
        {
            "distance_km": distance / 1000,
            "received_power_w": received,
            "photon_ceiling_gbps": photon_rate,
            "electronics_ceiling_gbps": electronics_rate,
            "screened_rate_gbps": np.minimum(photon_rate, electronics_rate),
            "full_rate_margin_db": margin,
            "full_rate_screen_pass": (margin >= 0) & (photon_rate >= electronics_rate),
            "one_way_propagation_us": distance / LIGHT_SPEED_M_S * 1e6,
        }
    )


def confocal_spatial_geometry(
    *,
    aperture_diameter_m: float = 0.1,
    wavelength_m: float = 1.55e-6,
    beams_per_axis: int = 1,
    wander_fraction: float = 0.1,
) -> dict[str, float | int]:
    """Paper's ideal L=pi*a²/lambda geometry; NOT a spatial link budget.

    An n-by-n layout uses diameter D/n per sub-aperture. Equal area packing,
    ideal beam quality and negligible truncation are assumed. Power sharing,
    crosstalk, terminal electronics and tracking still need separate validation.
    """
    _positive("aperture_diameter_m", aperture_diameter_m)
    _positive("wavelength_m", wavelength_m)
    _integer("beams_per_axis", beams_per_axis)
    if not np.isfinite(wander_fraction) or not 0 < wander_fraction <= 1:
        raise ValueError("wander_fraction must lie in (0, 1]")
    radius = aperture_diameter_m / (2 * beams_per_axis)
    distance = pi * radius**2 / wavelength_m
    return {
        "beam_count": beams_per_axis**2,
        "subaperture_diameter_m": 2 * radius,
        "ideal_distance_m": distance,
        "pointing_allowance_urad": wander_fraction * radius / distance * 1e6,
    }


@dataclass(frozen=True)
class FormationSpec:
    """Bounded planar HCW square lattice, independent of paper Fig. 2 data.

    x is radial and y along-track in the rotating LVLH frame. Every satellite
    shares the circular reference mean motion. This omits J2, drag, control,
    navigation errors, eclipses, occlusion and collision avoidance operations.
    """

    altitude_m: float = 650_000.0
    cluster_radius_m: float = 1000.0
    grid_side: int = 9

    def __post_init__(self) -> None:
        _positive("altitude_m", self.altitude_m)
        _positive("cluster_radius_m", self.cluster_radius_m)
        _integer("grid_side", self.grid_side, 3)
        if self.grid_side % 2 != 1 or self.grid_side > 31:
            raise ValueError("grid_side must be odd and <= 31")
        if self.cluster_radius_m > 0.001 * (6_371_000 + self.altitude_m):
            raise ValueError("HCW screening requires cluster radius <= 0.001 of orbital radius")


def hcw_formation(time_s, spec: FormationSpec | None = None) -> np.ndarray:
    """Return (time, satellite, 6) LVLH [x,y,z,vx,vy,vz] in m and m/s.

    x=A*cos(nt)+B*sin(nt), y=-2*A*sin(nt)+2*B*cos(nt) is the bounded
    solution of x''-2*n*y'-3*n²*x=0, y''+2*n*x'=0. The parameter lattice
    is scaled so no member ever exceeds cluster_radius_m in this model.
    """
    spec = FormationSpec() if spec is None else spec
    time = np.atleast_1d(np.asarray(time_s, dtype=float))
    if time.ndim != 1 or time.size == 0 or np.any(~np.isfinite(time)):
        raise ValueError("time_s must be a nonempty finite vector")
    half = spec.grid_side // 2
    a, b = np.meshgrid(np.arange(-half, half + 1), np.arange(-half, half + 1))
    scale = spec.cluster_radius_m / (2 * np.sqrt(2) * half)
    a, b = a.ravel() * scale, b.ravel() * scale
    n = 2 * pi / circular_orbit_period_s(spec.altitude_m)
    c, s = np.cos(n * time[:, None]), np.sin(n * time[:, None])
    x, y = a * c + b * s, -2 * a * s + 2 * b * c
    zero = np.zeros_like(x)
    return np.stack((x, y, zero, n * (-a * s + b * c), -2 * n * x, zero), axis=-1)


def formation_metrics(time_s, spec: FormationSpec | None = None) -> pd.DataFrame:
    """Sampled all-pairs minimum, cluster radius and neighbor link distances.

    Computes one timestep at a time to bound temporary memory. Sampled minima
    do not certify continuous collision clearance; spacecraft size is omitted.
    """
    spec = FormationSpec() if spec is None else spec
    time = np.atleast_1d(np.asarray(time_s, dtype=float))
    positions = hcw_formation(time, spec)[..., :3]
    grid = np.arange(spec.grid_side**2).reshape(spec.grid_side, spec.grid_side)
    left = np.r_[grid[:, :-1].ravel(), grid[:-1, :].ravel()]
    right = np.r_[grid[:, 1:].ravel(), grid[1:, :].ravel()]
    rows = []
    for t, xyz in zip(time, positions, strict=True):
        distance = np.linalg.norm(xyz[:, None] - xyz[None, :], axis=-1)
        np.fill_diagonal(distance, np.inf)
        neighbors = distance[left, right]
        rows.append(
            {
                "time_s": t,
                "sampled_min_separation_m": distance.min(),
                "cluster_radius_m": np.linalg.norm(xyz, axis=1).max(),
                "neighbor_min_m": neighbors.min(),
                "neighbor_max_m": neighbors.max(),
                "neighbor_max_one_way_us": neighbors.max() / LIGHT_SPEED_M_S * 1e6,
            }
        )
    return pd.DataFrame(rows)


def radiation_event_screen(
    *,
    annual_dose_rad_si: float,
    dose_per_event_rad_si: float,
    mission_years: float,
    device_count: int = 1,
    inferences_per_second_per_device: float = 1.0,
) -> dict[str, float]:
    """Conditional constant-rate Poisson extrapolation of a beam-test event.

    Events are not necessarily lost inferences. No mitigation, downtime or
    cross-device correlation is modeled. Input dose is supplied, not derived
    from orbit, shielding thickness or a solar-weather index.
    """
    _positive("annual_dose_rad_si", annual_dose_rad_si, zero=True)
    _positive("dose_per_event_rad_si", dose_per_event_rad_si)
    _positive("mission_years", mission_years)
    _positive("inferences_per_second_per_device", inferences_per_second_per_device)
    _integer("device_count", device_count)
    annual = annual_dose_rad_si / dose_per_event_rad_si
    expected = annual * mission_years * device_count
    per_inference = annual / (SECONDS_PER_YEAR * inferences_per_second_per_device)
    return {
        "mission_dose_rad_si": annual_dose_rad_si * mission_years,
        "events_per_device_year": annual,
        "expected_fleet_mission_events": expected,
        "probability_at_least_one_fleet_event": -expm1(-expected),
        "expected_events_per_inference": per_inference,
    }


def launch_learning_price(
    *,
    initial_price_usd_kg: float,
    initial_cumulative_mass_t: float,
    cumulative_mass_t: float,
    learning_rate: float = 0.2,
) -> float:
    """Wright curve C=C0*(M/M0)**log2(1-learning_rate), without a date forecast."""
    for name, value in (
        ("initial_price_usd_kg", initial_price_usd_kg),
        ("initial_cumulative_mass_t", initial_cumulative_mass_t),
        ("cumulative_mass_t", cumulative_mass_t),
    ):
        _positive(name, value)
    if cumulative_mass_t < initial_cumulative_mass_t:
        raise ValueError("cumulative mass must not precede the baseline")
    if not np.isfinite(learning_rate) or not 0 <= learning_rate < 1:
        raise ValueError("learning_rate must lie in [0, 1)")
    return initial_price_usd_kg * (cumulative_mass_t / initial_cumulative_mass_t) ** log2(
        1 - learning_rate
    )


def launched_power_cost(
    *, mass_kg: float, power_kw: float, lifetime_years: float, launch_price_usd_kg: float
) -> float:
    """Undiscounted launch-only USD per nameplate kW-year; not LCOE or TCO."""
    for name, value in (
        ("mass_kg", mass_kg),
        ("power_kw", power_kw),
        ("lifetime_years", lifetime_years),
    ):
        _positive(name, value)
    _positive("launch_price_usd_kg", launch_price_usd_kg, zero=True)
    return mass_kg * launch_price_usd_kg / (power_kw * lifetime_years)


def launch_energy_cost_parity(
    *,
    mass_kg: float,
    continuous_compute_kw: float,
    lifetime_years: float,
    electricity_usd_kwh: float,
    terrestrial_pue: float,
    utilization: float = 1.0,
) -> float:
    """Launch price equating launch-only cost with terrestrial electricity spend.

    Equal utilized compute electrical power is assumed, not equal useful work.
    Excludes spacecraft/chips, operations, replacement, financing and network.
    """
    for name, value in (
        ("mass_kg", mass_kg),
        ("continuous_compute_kw", continuous_compute_kw),
        ("lifetime_years", lifetime_years),
    ):
        _positive(name, value)
    _positive("electricity_usd_kwh", electricity_usd_kwh, zero=True)
    if not np.isfinite(terrestrial_pue) or terrestrial_pue < 1:
        raise ValueError("terrestrial_pue must be finite and >= 1")
    if not np.isfinite(utilization) or not 0 <= utilization <= 1:
        raise ValueError("utilization must lie in [0, 1]")
    return (
        electricity_usd_kwh
        * 8760
        * terrestrial_pue
        * utilization
        * continuous_compute_kw
        * lifetime_years
        / mass_kg
    )


def load_space_ai_evidence(path: str | Path | None = None) -> dict:
    """Load the packaged, manually curated v2 evidence snapshot or an override.

    Paper numbers retain locators and evidence status. This is not PDF parsing
    or a live hardware catalogue. The source PDF is not redistributed.
    """
    content = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("orbitalpv")
        .joinpath("_data/space_ai_2511_19468v2.json")
        .read_text(encoding="utf-8")
    )
    data = json.loads(content)
    if data.get("schema_version") != 1 or data.get("source", {}).get("paper_id") != "2511.19468v2":
        raise ValueError("Expected space-AI evidence schema 1 pinned to 2511.19468v2")
    for name in (
        "optical",
        "formation",
        "radiation",
        "economics",
        "solar_estimate",
        "engineering_assumptions",
    ):
        section = data.get(name)
        if (
            not isinstance(section, dict)
            or not section.get("locator")
            or not section.get("evidence_kind")
        ):
            raise ValueError(f"Missing evidence metadata: {name}")
    OpticalLinkSpec(**data["optical"]["inputs"])
    FormationSpec(**data["formation"]["inputs"])
    return data
