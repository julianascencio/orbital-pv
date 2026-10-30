"""Short, provenance-aware workflows for terrestrial PV image analysis."""

from __future__ import annotations

import importlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

import space_pv_connectors.ground_ghsl
import space_pv_connectors.ground_site

from .pv_detection import (
    PVFootprintPrediction,
    PVTrainingSample,
    build_pv_features,
    rasterize_pv_labels,
)
from .pv_inventory import PVCapacityModel, osm_pv_features


def prepare_pv_training_sample(
    site: space_pv_connectors.ground_site.PVSite,
    *,
    site_id: str | None = None,
    background_is_negative: bool = False,
    negative_geometries: Sequence[Mapping[str, Any]] | None = None,
    boundary_buffer_m: float = 20.0,
) -> PVTrainingSample:
    """Create explicit weak labels from mapped photovoltaic generator polygons.

    Plant perimeters and point-only locations are not panel labels. This
    adapter rejects sites without usable generator polygons; for reviewed
    labels or other source products use ``rasterize_pv_labels`` directly.
    Missing map features do not establish absence of PV. Opting into
    ``background_is_negative`` records that assumption in the label source.
    Explicit negative geometries use WGS84 longitude/latitude coordinates.
    """
    identifier = site.name if site_id is None else site_id
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("site_id must be a nonempty string")
    mapped = osm_pv_features(site.osm, require_photovoltaic=True)
    polygons = [
        feature["geometry"]
        for feature in mapped["features"]
        if feature["properties"]["element_kind"] == "generator"
        and feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    ]
    if not polygons:
        raise ValueError(
            "No mapped photovoltaic generator polygons; a plant boundary or missing OSM "
            "features cannot supply panel labels. Provide independently reviewed geometries."
        )
    features = build_pv_features(site.images)
    labels = rasterize_pv_labels(
        features,
        polygons,
        negative_geometries=negative_geometries,
        background_is_negative=background_is_negative,
        boundary_buffer_m=boundary_buffer_m,
    )
    if not np.any(labels == 1):
        raise ValueError("No usable positive pixel centres intersect the mapped array polygons")
    timestamp = site.osm.get("osm3s", {}).get("timestamp_osm_base", "unknown map date")
    label_source = (
        f"OSM photovoltaic generator polygons; map snapshot {timestamp}; "
        f"image {features.scene_id}; pixel-centre weak labels; "
        f"outside boundary buffer {boundary_buffer_m:g} m; "
        f"background_is_negative={background_is_negative}; "
        f"explicit_negative_polygons={len(negative_geometries or [])}; "
        "not independently surveyed ground truth"
    )
    return PVTrainingSample(features, labels, identifier, label_source)


def classify_pv_farms(
    farms: dict[str, Any], settlement: space_pv_connectors.ground_ghsl.SettlementRaster
) -> dict[str, Any]:
    """Attach historical GHSL context at each grouped farm's centroid.

    This explicit farm-centroid lookup differs from the original paper's
    majority of input-feature centroid flags. It is not an area fraction or
    a statement about present-day land use. Unknown cells retain None flags.
    The input GeoJSON is not modified.
    """
    if farms.get("type") != "FeatureCollection" or not isinstance(farms.get("features"), list):
        raise ValueError("farms must be a GeoJSON FeatureCollection from cluster_pv_farms")
    result = deepcopy(farms)
    points = [
        (feature["properties"]["centroid_lon"], feature["properties"]["centroid_lat"])
        for feature in result["features"]
    ]
    samples = settlement.sample_points(points)
    for feature, sample in zip(result["features"], samples, strict=True):
        feature["properties"]["settlement"] = sample
        feature["properties"]["urban"] = sample["urban"]
        feature["properties"]["water"] = sample["water"]
    result.setdefault("metadata", {})["settlement_context"] = {
        "epoch": settlement.epoch,
        "edition": settlement.edition,
        "sampling": "grouped farm centroid, not majority of original feature centroids",
        "source": deepcopy(settlement.provenance),
    }
    return result


def estimate_pv_farm_capacity(farms: dict[str, Any], model: PVCapacityModel) -> dict[str, Any]:
    """Attach calibrated capacities while retaining reasons for withheld values.

    A farm needs a positive capacity-area predictor with the same definition
    as the calibration and an explicit nonurban flag. Different area bases,
    absent areas, unknown/urban context and out-of-range predictors are kept
    in the inventory with null estimates. No extrapolation is enabled here.
    """
    if farms.get("type") != "FeatureCollection" or not isinstance(farms.get("features"), list):
        raise ValueError("farms must be a GeoJSON FeatureCollection from cluster_pv_farms")
    result = deepcopy(farms)
    for feature in result["features"]:
        props = feature["properties"]
        area = props.get("capacity_area_m2")
        record = {
            "estimated_capacity_mw": None,
            "capacity_lower_mw": None,
            "capacity_upper_mw": None,
            "capacity_basis": model.capacity_basis,
            "capacity_extrapolated": False,
            "capacity_estimate_status": "missing_area",
        }
        if area is not None and math.isfinite(area) and area > 0:
            basis = props.get("capacity_area_basis")
            if basis != model.area_basis:
                record["capacity_estimate_status"] = "area_definition_mismatch"
            else:
                prediction = model.predict([area], urban=[props.get("urban")], area_basis=basis)
                record["capacity_extrapolated"] = bool(prediction.extrapolated[0])
                record["capacity_estimate_status"] = prediction.reasons[0]
                if prediction.eligible[0]:
                    record.update(
                        estimated_capacity_mw=float(prediction.mean_mw[0]),
                        capacity_lower_mw=float(prediction.lower_mw[0]),
                        capacity_upper_mw=float(prediction.upper_mw[0]),
                    )
        props.update(record)
    result.setdefault("metadata", {})["capacity_model"] = asdict(model)
    result["metadata"]["capacity_interval"] = (
        "Approximate 95% Gaussian prediction interval; residual homoscedasticity "
        "and local linearization assumed, truncated at zero"
    )
    return result


def save_pv_prediction(
    prediction: PVFootprintPrediction,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Export WGS84 GeoJSON, native-grid scores/mask, and prediction metadata.

    ``pv_prediction.tif`` contains float32 class scores in band 1 and a
    0/1 area-filtered mask in band 2; invalid pixels have nodata -9999 in both.
    This is a derived model output, not a raw Sentinel-2 asset. Model weights
    are saved separately with ``PVFootprintModel.save``. Existing outputs
    require explicit overwrite, and a partial failure can leave earlier
    completed files in the destination directory.
    """
    if not isinstance(overwrite, bool):
        raise ValueError("overwrite must be a bool")
    directory = Path(destination)
    paths = {
        "geojson": directory / "pv_footprints.geojson",
        "raster": directory / "pv_prediction.tif",
        "metadata": directory / "pv_prediction.json",
    }
    if not overwrite and any(path.exists() for path in paths.values()):
        raise FileExistsError(
            "Prediction output already exists; choose a new directory or overwrite"
        )
    try:
        rio = importlib.import_module("rasterio")
    except ImportError as exc:
        raise ImportError("Install 'orbital-pv[ground]' to export prediction GeoTIFFs") from exc
    metadata = prediction.metadata
    if prediction.probabilities.shape != prediction.mask.shape or prediction.mask.ndim != 2:
        raise ValueError("Prediction scores and mask must share a two-dimensional grid")
    # Serialize before writing anything, so invalid metadata cannot leave a partial export.
    geojson_text = json.dumps(prediction.geojson, indent=2, allow_nan=False)
    metadata_text = json.dumps(metadata, indent=2, allow_nan=False)
    transform = rio.Affine(*metadata["transform"])
    crs = rio.crs.CRS.from_user_input(metadata["crs"])
    directory.mkdir(parents=True, exist_ok=True)
    nodata = -9999.0
    values = np.stack(
        [
            np.ma.filled(prediction.probabilities.astype(np.float32), nodata),
            np.ma.filled(prediction.mask.astype(np.float32), nodata),
        ]
    )
    with rio.open(
        paths["raster"],
        "w",
        driver="GTiff",
        height=values.shape[1],
        width=values.shape[2],
        count=2,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=nodata,
        compress="deflate",
    ) as raster:
        raster.write(values)
        raster.set_band_description(1, "PV class score (uncalibrated random-forest probability)")
        raster.set_band_description(2, "Predicted PV mask after minimum-area filtering")
        raster.update_tags(
            model_id=metadata["model_id"],
            scene_id=metadata["scene_id"],
            inference_uses_osm="false",
            area_semantics=metadata["area_semantics"],
        )
    paths["geojson"].write_text(geojson_text + "\n")
    paths["metadata"].write_text(metadata_text + "\n")
    return paths
