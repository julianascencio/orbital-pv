"""Reproduce an observed MetOp profile and an independent Earth-view benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv import environment_data as opv

HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = "ce9fed0c05814b73fb244a0b7decf6c23be1c1abc74794c843dd8f3195ee2f44"
PROTON = "mep_pro_tel0_flux_p1"
ELECTRON = "mep_ele_tel0_flux_e1"


def make_snapshot(raw: Path, output: Path) -> dict:
    """Reduce one verified source day into per-minute medians, retaining units."""
    if hashlib.sha256(raw.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("NOAA source differs from the pinned reference input")
    source = opv.read_poes_metop(raw, channels=[PROTON, ELECTRON, "lat", "lon"])
    time = pd.DatetimeIndex(source.timestamp_utc).floor("min")
    flux = source[[PROTON, ELECTRON]].where(source[[PROTON, ELECTRON]] >= 0)
    flux.index = time
    group = flux.groupby(level=0)
    reduced = group.median().rename(
        columns={
            PROTON: "proton_39kev_median_per_cm2_s_sr_kev",
            ELECTRON: "electron_gt40kev_median_per_cm2_s_sr",
        }
    )
    reduced["proton_valid_samples"] = group[PROTON].count()
    reduced["electron_valid_samples"] = group[ELECTRON].count()
    # Track coordinates describe the first observed sample of each bin, not a
    # circularly invalid average of longitudes across the dateline.
    track = source.assign(minute=time).groupby("minute", sort=True).first()
    reduced["first_sample_latitude_deg"] = track["lat"]
    reduced["first_sample_longitude_deg"] = track["lon"]
    output.mkdir(parents=True, exist_ok=True)
    path = output / "metop01_20230101_minutes.csv"
    reduced.to_csv(path, index_label="minute_utc", float_format="%.8g")
    provenance = {
        "source": "NOAA NCEI POES/MetOp SEM-2",
        "license": "Public (provider file metadata)",
        "url": opv.PoesMetopConnector.daily_url("metop01", "2023-01-01"),
        "raw_sha256": SOURCE_SHA256,
        "raw_bytes": raw.stat().st_size,
        "raw_samples": len(source),
        "source_start_utc": source.timestamp_utc.iloc[0].isoformat(),
        "source_end_utc": source.timestamp_utc.iloc[-1].isoformat(),
        "native_time_encoding": source.attrs["time_encoding"],
        "provider_processing_level": source.attrs["provider_attributes"].get("processing_level"),
        "source_channels": {
            PROTON: source.attrs["units"][PROTON],
            ELECTRON: source.attrs["units"][ELECTRON],
        },
        "transformation": "UTC minute medians of nonnegative flux; per-channel valid counts; first observed track coordinate per minute",
        "snapshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "snapshot_rows": len(reduced),
        "limits": "Provider reports known contamination; channels have different energy definitions/units. No contamination correction, angular integration, dose, NIEL or solar-cell retention inference.",
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    return provenance


def earth_benchmark() -> pd.DataFrame:
    """Uniform 240 W/m2 hemispheric flux is a declared analytic scenario."""
    radius = 6_371_008.8
    lat_edges, lon_edges = np.linspace(-90, 90, 361), np.linspace(-180, 180, 721)
    areas = opv.earth_grid_cell_areas(lat_edges, lon_edges)
    latitude, longitude = np.meshgrid(
        (lat_edges[1:] + lat_edges[:-1]) / 2, (lon_edges[1:] + lon_edges[:-1]) / 2, indexing="ij"
    )
    records = []
    for angle in range(0, 181, 15):
        theta = np.deg2rad(angle)
        result = opv.earth_flux_to_panel(
            [radius + 550_000, 0, 0],
            [-np.cos(theta), np.sin(theta), 0],
            latitude,
            longitude,
            np.full(areas.shape, 240.0),
            areas,
        )
        records.append(
            {"panel_angle_from_nadir_deg": angle, "earth_ir_on_panel_w_m2": result.irradiance_w_m2}
        )
    return pd.DataFrame(records)


def run(output: Path, *, snapshot_dir: Path = HERE / "data") -> dict:
    provenance = json.loads((snapshot_dir / "provenance.json").read_text(encoding="utf-8"))
    path = snapshot_dir / "metop01_20230101_minutes.csv"
    if hashlib.sha256(path.read_bytes()).hexdigest() != provenance["snapshot_sha256"]:
        raise ValueError("Environmental observation snapshot checksum failed")
    observations = pd.read_csv(path)
    earth = earth_benchmark()
    analytic = 240 * (6_371_008.8 / (6_371_008.8 + 550_000)) ** 2
    summary = {
        "observed_data": {
            "raw_samples": provenance["raw_samples"],
            "minute_bins": len(observations),
            "proton_median_per_cm2_s_sr_kev": float(
                observations.proton_39kev_median_per_cm2_s_sr_kev.median()
            ),
            "electron_median_per_cm2_s_sr": float(
                observations.electron_gt40kev_median_per_cm2_s_sr.median()
            ),
            "provenance": provenance,
        },
        "earth_view_benchmark": {
            "kind": "uniform Lambertian Earth scenario, not a CERES measurement",
            "outgoing_flux_w_m2": 240.0,
            "altitude_m": 550_000,
            "nadir_analytic_w_m2": analytic,
            "nadir_numerical_w_m2": float(earth.earth_ir_on_panel_w_m2.iloc[0]),
            "relative_error": float(abs(earth.earth_ir_on_panel_w_m2.iloc[0] / analytic - 1)),
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    earth.to_csv(output / "earth_view_benchmark.csv", index=False)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/environmental_inputs"))
    parser.add_argument(
        "--download", action="store_true", help="Regenerate the checked-in snapshot from NOAA"
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/environmental_inputs"))
    args = parser.parse_args()
    if args.download:
        raw = args.cache_dir / "poes_m01_20230101_proc.nc"
        with opv.PoesMetopConnector() as connector:
            connector.fetch_day("metop01", "2023-01-01", raw, expected_sha256=SOURCE_SHA256)
        make_snapshot(raw, HERE / "data")
    print(json.dumps(run(args.output), indent=2, allow_nan=False))
