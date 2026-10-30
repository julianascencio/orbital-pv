"""Real historical capacity holdout with separate country calibration and geometry limits."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import orbitalpv as opv
from orbitalpv.ground_research import (
    evaluate_geometry_capacity,
    fit_geometry_capacity_model,
    summarize_pv_geometry,
)


def run(data: Path, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Choose an empty analysis output directory")
    source = data / "wiki_solar_join.csv"
    provenance = json.loads(source.with_suffix(".csv.meta.json").read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest() != provenance["sha256"]:
        raise ValueError("Historical reference checksum mismatch")
    raw = pd.read_csv(source)
    valid = (
        np.isfinite(raw.power)
        & (raw.power > 0)
        & np.isfinite(raw["panel.area"])
        & (raw["panel.area"] > 0)
        & raw.GID_0.notna()
    )
    frame = raw.loc[valid].assign(
        site_id=lambda f: f.sol_id.astype(str),
        footprint_area_m2=lambda f: f["panel.area"] * 1e6,
        capacity_mw=lambda f: f.power,
    )
    # These country groups are declared a priori, not selected by Spain error.
    calibration_countries = ("FRA", "CAN", "ITA")
    training = frame[~frame.GID_0.isin((*calibration_countries, "ESP"))]
    calibration = frame[frame.GID_0.isin(calibration_countries)]
    test = frame[frame.GID_0 == "ESP"]
    model = fit_geometry_capacity_model(
        training,
        calibration,
        capacity_basis="reported",
        area_basis="OSM polygon proxy",
        source="Dunnett2020 Figshare v2 Wiki Solar historical reference",
        group_column="GID_0",
    )
    metrics = evaluate_geometry_capacity(model, test)
    prediction = model.predict(test, area_basis="OSM polygon proxy", allow_extrapolation=True)
    prediction["reference_capacity_mw"] = test.capacity_mw.to_numpy()
    prediction["country"] = test.GID_0.to_numpy()
    prediction["footprint_area_m2"] = test.footprint_area_m2.to_numpy()
    output.mkdir(parents=True, exist_ok=True)
    prediction.to_csv(output / "spain_capacity_holdout.csv", index=False)
    (output / "capacity_model.json").write_text(
        json.dumps(asdict(model), indent=2, allow_nan=False) + "\n"
    )
    # Geometry from the same licensed OSM cache; it remains an inferred axis,
    # not a measurement of installed panel tilt, facing azimuth or module area.
    configuration = json.loads((data / "pv-sites.json").read_text())
    geometry_counts = {}
    for name in ("cestas", "tenerife"):
        site = opv.load_pv_site(
            **configuration[name], cache_dir=data, offline=True, assets=("red",)
        )
        features = opv.osm_pv_features(site.osm)
        geometry = summarize_pv_geometry(features)
        geometry.to_json(output / f"{name}_geometry.json", orient="records", indent=2)
        geometry_counts[name] = len(geometry)
    report = {
        "data_kind": "real historical reported capacity reference and cached OSM geometries",
        "metrics": metrics,
        "input_rows": len(raw),
        "excluded_invalid_rows": int((~valid).sum()),
        "split": {
            "training_sites": len(training),
            "calibration_sites": len(calibration),
            "test_sites": len(test),
            "calibration_countries": list(calibration_countries),
            "test_country": "ESP",
        },
        "capacity_basis": "reported; historical source does not consistently distinguish AC/DC",
        "interval_caveat": "split conformal assumes exchangeability; geographic shift means measured holdout coverage is essential",
        "geometry_caveat": "polygon long axis modulo 180; no actual panel tilt or facing direction inferred",
        "geometry_feature_counts": geometry_counts,
        "reference_provenance": provenance,
        "license": "Original reference source terms retained in provenance; OpenStreetMap ODbL attribution",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    ordered = prediction.sort_values("reference_capacity_mw")
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    x = np.arange(len(ordered))
    ax.fill_between(
        x, ordered.lower_mw, ordered.upper_mw, alpha=0.2, label="90% nominal calibrated interval"
    )
    ax.plot(x, ordered.capacity_mw, label="Geometry regression")
    ax.scatter(x, ordered.reference_capacity_mw, s=9, color="black", label="Historical reported MW")
    ax.set(
        xlabel="Held-out Spain sites ordered by reference capacity",
        ylabel="Reported-basis capacity (MW)",
        yscale="log",
        title=f"Spain holdout: observed interval coverage {metrics['coverage_observed']:.1%}",
    )
    ax.legend(fontsize=8)
    fig.savefig(output / "capacity_coverage.png", dpi=160)
    plt.close(fig)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "examples/ground_imagery/_data",
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/pv_geometry_capacity"))
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.output)["metrics"], indent=2))
