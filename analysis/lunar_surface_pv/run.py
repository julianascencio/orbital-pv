"""Offline lunar terrain, power, storage, thermal and mobility experiments.

All power/engineering results are scenarios driven by measured/interpolated
terrain, binned radiometry and computed SPICE geometry. No measured lunar PV
output or flight-design validation is implied. See README.md for assumptions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from orbitalpv import PvwattsReference, lunar, physics

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "examples/lunar/_data"
REFERENCE = PvwattsReference(1361 * 0.28, -0.002, 1361)  # illustrative 1 m² AM0 array


@lru_cache
def inputs() -> dict:
    manifest = json.loads((DATA / "provenance.json").read_text())
    for name, record in manifest["files"].items():
        if hashlib.sha256((DATA / name).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Lunar input checksum mismatch: {name}")
    return manifest


@lru_cache
def terrain(name: str) -> lunar.LunarTerrain:
    inputs()
    with np.load(DATA / name, allow_pickle=False) as data:
        return lunar.LunarTerrain(data["x_m"], data["y_m"], data["elevation_m"])


@lru_cache
def ephemeris(period: str = "year") -> pd.DataFrame:
    inputs()
    if period not in {"year", "month"}:
        raise ValueError("period must be year or month")
    return pd.read_csv(DATA / f"{period}_2026_ephemeris.csv")


def point(site: str) -> tuple[float, float, float]:
    metadata = inputs()["sites"][site]
    x, y = metadata["x_m"], metadata["y_m"]
    return x, y, terrain(f"site{site}_5m.npz").height(x, y)


def horizon_at(site: str, x: float, y: float, height: float, *, bins: int = 180) -> pd.DataFrame:
    fine = terrain(f"site{site}_5m.npz")
    ground = fine.height(x, y)
    layers = []
    # For off-centre map/route points the fine window has less directional extent;
    # only exclude the inner radius guaranteed to be covered by that window.
    inner = max(0, min(x - fine.x_m[0], fine.x_m[-1] - x, y - fine.y_m[0], fine.y_m[-1] - y) - 20)
    for name, minimum in [
        (f"site{site}_5m.npz", 0),
        (f"site{site}_80m.npz", inner),
        ("regional_1280m.npz", 18000),
    ]:
        layers.append(
            lunar.terrain_horizon(
                terrain(name),
                site_x_m=x,
                site_y_m=y,
                tower_height_m=height,
                azimuth_bins=bins,
                site_elevation_m=ground,
                minimum_distance_m=minimum,
            )
        )
    result = layers[0].copy()
    result["horizon_elevation_deg"] = np.maximum.reduce(
        [layer.horizon_elevation_deg.to_numpy() for layer in layers]
    )
    result.attrs.update(
        model="5 m / 80 m / 1280 m sector envelope; shared fine-grid observer elevation",
        minimum_directional_extent_m=layers[-1].attrs["minimum_directional_extent_m"],
    )
    return result


@lru_cache
def site_horizon(site: str, height: float, bins: int = 180) -> pd.DataFrame:
    x, y, _ = point(site)
    return horizon_at(site, x, y, height, bins=bins)


@lru_cache
def geometry_at(x: float, y: float, elevation: float, period: str = "year") -> pd.DataFrame:
    eph = ephemeris(period)
    longitude, latitude = lunar.south_polar_lonlat(x, y)
    return lunar.lunar_solar_geometry(
        eph[[f"sun_{axis}_m" for axis in "xyz"]].to_numpy(),
        eph[[f"earth_{axis}_m" for axis in "xyz"]].to_numpy(),
        longitude_deg=float(longitude),
        latitude_deg=float(latitude),
        elevation_m=elevation,
    )


@lru_cache
def profile(
    site: str = "01",
    height: float = 5,
    mode: Literal["fixed", "azimuth_tracking", "sun_tracking"] = "sun_tracking",
    period: str = "year",
) -> pd.DataFrame:
    x, y, ground = point(site)
    g = geometry_at(x, y, ground + height, period)
    frame = lunar.lunar_pv_power(
        g,
        site_horizon(site, height),
        reference=REFERENCE,
        cell_temperature_c=25,
        mode=mode,
        tilt_deg=90,
        panel_azimuth_deg=0,
    )
    frame["time_s"] = ephemeris(period).time_s
    frame["utc"] = ephemeris(period).utc
    return frame


def compare_sites() -> pd.DataFrame:
    rows = []
    for site in inputs()["sites"]:
        for height in (2, 5, 20):
            for mode in ("fixed", "sun_tracking"):
                p = profile(site, height, mode)
                hours = np.diff(p.time_s) / 3600
                visible = (p.terrain_visible_fraction * p.earth_visible_fraction).to_numpy()[:-1]
                energy = float(p.dc_power_w.to_numpy()[:-1] @ hours)
                rows.append(
                    dict(
                        site=site,
                        tower_height_m=height,
                        mode=mode,
                        energy_kwh_m2=energy / 1000,
                        mean_visible_fraction=float(np.average(visible, weights=hours)),
                        longest_darkness_h=lunar.longest_darkness_hours(p.time_s, visible),
                        model="2026 geometric scenario; constant 25 C cells; 2h step",
                    )
                )
    return pd.DataFrame(rows)


def temperature_observations() -> pd.DataFrame:
    inputs()
    frame = lunar.parse_diviner_pcp(
        (DATA / "diviner_subset.tab").read_bytes(),
        (DATA / "diviner_label.xml").read_bytes(),
        allow_subset=True,
    )
    sites = list(inputs()["sites"])
    distance = np.array(
        [np.hypot(frame.x_m - point(site)[0], frame.y_m - point(site)[1]) for site in sites]
    )
    frame["site"] = np.array(sites)[distance.argmin(axis=0)]
    frame["distance_from_site_m"] = distance.min(axis=0)
    return frame


def thermal_case(site: str = "01") -> tuple[pd.DataFrame, pd.DataFrame]:
    p = profile(site, 5, "sun_tracking", "month")
    observed = temperature_observations()
    nearby = observed[(observed.site == site) & (observed.distance_from_site_m < 800)]
    # Three constant measured-spatial-percentile scenarios, NOT a reconstructed
    # time history or the ground temperature at this precise array position.
    rows = []
    for quantile in (0.1, 0.5, 0.9):
        ground_k = float(nearby.temperature_k.quantile(quantile))
        result = lunar.lunar_panel_thermal(
            p.time_s,
            p.poa_direct_w_m2,
            ground_temperature_k=ground_k,
            ground_view_factor=0.5,
            ground_emissivity=1.0,
            surface=physics.ThermalSurface(heat_capacity_j_k=10000),
            pv_efficiency=0.28,
            initial_temperature_k=250,
            max_step_s=300,
        )
        result["ground_scenario_quantile"] = quantile
        rows.append(result)
    return pd.concat(rows, ignore_index=True), nearby


@lru_cache
def storage_cases(site: str = "01", height: float = 5) -> pd.DataFrame:
    p = profile(site, height)
    # 1 kW payload plus explicit, constant equivalent-loss heater scenario.
    heater = float(
        lunar.survival_heater_power(
            100, setpoint_k=253, thermal_conductance_w_k=1, internal_heat_w=50
        )
    )
    return lunar.size_lunar_storage(
        p.time_s,
        p.dc_power_w.to_numpy()[:-1],
        1000 + heater,
        array_areas_m2=[6, 10, 16, 25, 40],
        capacities_wh=np.array([20, 50, 100, 200, 400, 800]) * 1000,
        battery_template=physics.BatterySpec(
            1,
            initial_soc=0.5,
            minimum_soc=0.1,
            maximum_soc=0.95,
            max_charge_w=15000,
            max_discharge_w=3000,
        ),
    )


def tower_tradeoff(site: str = "01") -> pd.DataFrame:
    """Lowest panel+battery+illustrative tower mass on the explicit candidate grid."""
    rows = []
    for height in (2, 5, 20):
        feasible = storage_cases(site, height).query("feasible")
        if feasible.empty:
            rows.append(dict(site=site, tower_height_m=height, feasible=False))
            continue
        best = feasible.iloc[0].to_dict()
        # Assumed 20 kg base + 5 kg/metre. This is not a structural design.
        tower_mass = 20 + 5 * height
        best.update(
            site=site,
            tower_height_m=height,
            tower_mass_kg=tower_mass,
            total_scenario_mass_kg=best["scenario_mass_kg"] + tower_mass,
        )
        rows.append(best)
    return pd.DataFrame(rows)


def resolution_sensitivity(site: str = "01") -> pd.DataFrame:
    """Report numerical sensitivity, not statistical confidence intervals."""
    x, y, ground = point(site)
    rows = []
    for bins in (90, 180, 360):
        for period, step in (("year", 2.0), ("month", 0.5)):
            g = geometry_at(x, y, ground + 5, period)
            p = lunar.lunar_pv_power(
                g,
                site_horizon(site, 5, bins),
                reference=REFERENCE,
                cell_temperature_c=25,
                mode="sun_tracking",
            )
            times = ephemeris(period).time_s.to_numpy()
            start = 181 * 86400 if period == "year" else 0
            keep = (times >= start) & (times <= start + 30 * 86400)
            times = times[keep]
            powers = p.dc_power_w.to_numpy()[keep][:-1]
            visibility = (p.terrain_visible_fraction * p.earth_visible_fraction).to_numpy()[keep][
                :-1
            ]
            rows.append(
                dict(
                    azimuth_bins=bins,
                    timestep_h=step,
                    july_30day_energy_kwh_m2=float(powers @ (np.diff(times) / 3600) / 1000),
                    longest_darkness_h=lunar.longest_darkness_hours(times, visibility),
                )
            )
    return pd.DataFrame(rows)


def yield_map(site: str = "01", samples: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Local annual tracking-yield map; small explicit grid for offline examples."""
    x, y, _ = point(site)
    xs, ys = x + np.linspace(-350, 350, samples), y + np.linspace(-350, 350, samples)
    output = np.empty((samples, samples))
    hours = np.diff(ephemeris().time_s) / 3600
    for j, yy in enumerate(ys):
        for i, xx in enumerate(xs):
            ground = terrain(f"site{site}_5m.npz").height(xx, yy)
            g = geometry_at(xx, yy, ground + 5)
            p = lunar.lunar_pv_power(
                g,
                horizon_at(site, xx, yy, 5),
                reference=REFERENCE,
                cell_temperature_c=25,
                mode="sun_tracking",
            )
            output[j, i] = p.dc_power_w.to_numpy()[:-1] @ hours / 1000
    return xs, ys, output


def rover_inputs(
    site: str = "01",
) -> tuple[lunar.LunarTerrain, np.ndarray, np.ndarray, lunar.LunarRover]:
    """Terrain and a deterministic mixed-light window for the routing example."""
    x, y, _ = point(site)
    fine = terrain(f"site{site}_5m.npz")
    spacing = 50.0
    xs, ys = x + np.arange(-3, 4) * spacing, y + np.arange(-3, 4) * spacing
    z = np.array([[fine.height(xx, yy) for xx in xs] for yy in ys])
    # Choose the 12h window starting at the largest spatial solar-power spread,
    # bounded so a full window remains. This deliberately illustrates mixed
    # light, not representative mission performance. Shadows are never invented.
    steps = 24
    full_time = ephemeris("month").time_s.to_numpy()
    solar = np.empty((len(full_time) - 1, len(ys), len(xs)))
    for j, yy in enumerate(ys):
        for i, xx in enumerate(xs):
            g = geometry_at(xx, yy, z[j, i] + 1, "month").iloc[:-1]
            pv = lunar.lunar_pv_power(
                g,
                horizon_at(site, xx, yy, 1, bins=90),
                reference=REFERENCE,
                cell_temperature_c=25,
                mode="sun_tracking",
            )
            solar[:, j, i] = 0.3 * pv.dc_power_w.to_numpy()
    spread = np.ptp(solar, axis=(1, 2))
    start_index = int(np.argmax(spread[: len(spread) - steps + 1]))
    time = full_time[start_index : start_index + steps + 1] - full_time[start_index]
    solar = solar[start_index : start_index + steps]
    rover = lunar.LunarRover(
        mass_kg=100,
        speed_m_s=0.1,
        capacity_wh=150,
        initial_energy_wh=90,
        reserve_wh=40,
        maximum_slope_deg=25,
    )
    return lunar.LunarTerrain(xs, ys, z), time, solar, rover


def rover_case(site: str = "01") -> tuple[pd.DataFrame, lunar.LunarTerrain, np.ndarray]:
    """Small physical routing scenario on measured terrain and simulated shadows."""
    grid, time, solar, rover = rover_inputs(site)
    path = lunar.energy_aware_route(
        grid.elevation_m,
        time,
        solar,
        cell_size_m=float(np.diff(grid.x_m)[0]),
        start=(6, 0),
        goal=(6, 6),
        rover=rover,
        heater_power_w=10,
    )
    return path, grid, solar


def main(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    summary = compare_sites()
    summary.to_csv(output / "sites_and_towers.csv", index=False)
    for site in inputs()["sites"]:
        storage_cases(site).to_csv(output / f"storage_site{site}.csv", index=False)
        tower_tradeoff(site).to_csv(output / f"tower_tradeoff_site{site}.csv", index=False)
    resolution_sensitivity().to_csv(output / "resolution_sensitivity.csv", index=False)
    thermal, observations = thermal_case()
    thermal.to_csv(output / "thermal_site01.csv", index=False)
    observations.to_csv(output / "diviner_near_site01.csv", index=False)
    xs, ys, energy = yield_map()
    pd.DataFrame(energy, index=ys, columns=xs).to_csv(output / "yield_map_site01.csv")
    route, _, _ = rover_case()
    route.to_csv(output / "rover_route_site01.csv", index=False)
    report = {
        "data_kind": "model scenarios; no lunar PV measurements",
        "input_manifest_sha256": hashlib.sha256(
            (DATA / "provenance.json").read_bytes()
        ).hexdigest(),
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sites": summary.to_dict(orient="records"),
        "thermal_max_balance_error_j": float(thermal.energy_balance_error_j.abs().max()),
        "route_arrival_h": float(route.time_s.iloc[-1] / 3600),
        "route_final_energy_wh": float(route.energy_wh.iloc[-1]),
        "limits": [
            "2h year, 30min month; finite window and resolution",
            "terrain interpolation and omitted subpixel obstacles",
            "constant cell temperature in yield/storage sweeps; separate coupled thermal experiment",
            "Diviner fixed spatial-temperature scenarios, not dated predictions",
            "illustrative equipment and mass assumptions; not a mission design",
        ],
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(summary.to_string(index=False))
    print(f"Wrote reproducible results to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/lunar_surface_pv")
    main(parser.parse_args().output)
