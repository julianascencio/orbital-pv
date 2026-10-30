"""Reproduce the terrestrial PV detection and inventory examples offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

import orbitalpv as opv


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def run(data: Path, output: Path) -> dict[str, Any]:
    """Write a complete reproducible analysis to an empty output directory."""
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Output directory is not empty; choose a new destination")
    configuration = json.loads((data / "pv-sites.json").read_text())
    csv = data / "wiki_solar_join.csv"
    reference_source = json.loads(csv.with_suffix(".csv.meta.json").read_text())
    if hashlib.sha256(csv.read_bytes()).hexdigest() != reference_source["sha256"]:
        raise ValueError("The capacity calibration snapshot checksum does not match")
    sites = {
        name: opv.load_pv_site(
            **settings,
            cache_dir=data,
            offline=True,
            assets=("visual", "scl", *opv.PV_SPECTRAL_BANDS),
        )
        for name, settings in configuration.items()
    }
    training = opv.prepare_pv_training_sample(
        sites["cestas"], site_id="cestas", background_is_negative=True
    )
    detector = opv.PVFootprintModel.fit([training], random_state=0)
    reference = opv.prepare_pv_training_sample(
        sites["tenerife"], site_id="tenerife", background_is_negative=True
    )
    image_metrics = detector.evaluate(
        reference.features,
        reference.labels,
        site_id=reference.site_id,
        label_source=reference.label_source,
    )
    capacity_data = pd.read_csv(csv)
    capacity_training = capacity_data[capacity_data.GID_0 != "ESP"]
    held_out = capacity_data[capacity_data.GID_0 == "ESP"]
    capacity_model = opv.fit_pv_capacity_model(
        capacity_training["panel.area"].to_numpy() * 1e6,
        capacity_training.power.to_numpy(),
        urban=capacity_training.urban.astype(bool).tolist(),
        capacity_basis="reported",
        area_basis="osm_polygon_proxy",
        source="Dunnett2020 Figshare v2 Wiki Solar; Spain withheld",
    )
    capacity_prediction = capacity_model.predict(
        held_out["panel.area"].to_numpy() * 1e6,
        urban=held_out.urban.astype(bool).tolist(),
        area_basis="osm_polygon_proxy",
    )
    capacity_metrics = opv.evaluate_pv_capacity(held_out.power.to_numpy(), capacity_prediction)
    output.mkdir(parents=True, exist_ok=True)
    detector.save(output / "footprint_model.json")
    _write(output / "capacity_model.json", asdict(capacity_model))
    _write(output / "image_validation.json", image_metrics)
    _write(output / "capacity_validation.json", capacity_metrics)
    exported = held_out[["sol_id", "GID_0", "power", "panel.area"]].copy()
    exported["estimated_capacity_mw"] = capacity_prediction.mean_mw
    exported["lower_mw"] = capacity_prediction.lower_mw
    exported["upper_mw"] = capacity_prediction.upper_mw
    exported["status"] = capacity_prediction.reasons
    exported.to_csv(output / "capacity_spain_holdout.csv", index=False)
    site_summaries = {}
    for name, site in sites.items():
        destination = output / name
        destination.mkdir()
        mapped = opv.osm_pv_features(site.osm)
        settlement = opv.load_settlement_raster(data / f"{name}-ghsl.tif")
        for profile in ("semantic", "dunnett2020"):
            farms = opv.classify_pv_farms(opv.cluster_pv_farms(mapped, profile=profile), settlement)
            farms = opv.estimate_pv_farm_capacity(farms, capacity_model)
            _write(destination / f"farms_{profile}.geojson", farms)
        site_summaries[name] = site.summary()
        if name == "cestas":
            continue
        prediction = detector.predict(opv.build_pv_features(site.images))
        opv.save_pv_prediction(prediction, destination)
        fig, _ = opv.plot_pv_detection(
            site,
            prediction,
            reference_labels=reference.labels if name == "tenerife" else None,
            reference_label="OSM weak reference",
            reference_credit="© OpenStreetMap contributors (ODbL) · Map snapshot 30 October 2026",
        )
        fig.savefig(destination / "prediction.png", dpi=150)
        plt.close(fig)
        site_summaries[name]["predicted_area_m2"] = prediction.area_m2
        site_summaries[name]["inference_uses_osm"] = False
    summary = {
        "image_validation": image_metrics,
        "capacity_validation": capacity_metrics,
        "sites": site_summaries,
        "interpretation": {
            "detector": "Research baseline; one training site; weak OSM reference, not surveyed accuracy",
            "capacity": "Historical reported-MW area proxy; AC/DC unspecified; country transfer errors reported",
            "settlement": "2015 epoch R2023A; farm-centroid lookup; not the original 2019 edition",
            "rengo": "Transfer illustration without panel-level reference; no accuracy score claimed",
        },
        "versions": {
            name: version(name)
            for name in ("numpy", "scikit-learn", "scipy", "rasterio", "shapely", "pyproj")
        },
        "inputs_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(data.iterdir())
            if path.is_file() and path.suffix in {".json", ".csv", ".tif"}
        },
        "capacity_reference": reference_source,
        "configuration": configuration,
    }
    _write(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "examples/ground_imagery/_data",
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/ground_pv_mapping"))
    args = parser.parse_args()
    result = run(args.data, args.output)
    print(
        json.dumps(
            {key: result[key] for key in ("image_validation", "capacity_validation")}, indent=2
        )
    )
    print(f"Outputs written to {args.output.resolve()}")
