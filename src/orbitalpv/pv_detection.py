"""Supervised, image-only PV footprint inference on explicit spectral inputs.

This is a trainable random-forest baseline, not a pretrained global detector
or an implementation of Dunnett et al.'s OSM inventory method. Labels must be
provided by the caller. In particular, absence from OSM is not a negative
label unless that assumption is explicitly chosen and recorded by the user.

Reflectance bands are aligned to the red band's grid. This derived feature
stack is separate from the untouched native ``GroundImage`` objects. Model
scores are forest class scores, not calibrated detection probabilities.
"""

from __future__ import annotations

import importlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np

from space_pv_connectors.ground_raster import GroundImage

PV_SPECTRAL_BANDS = ("blue", "green", "red", "nir", "swir16", "swir22")
PV_FEATURE_NAMES = (*PV_SPECTRAL_BANDS, "ndvi", "ndbi", "mndwi")
DEFAULT_EXCLUDED_SCL = (0, 1, 2, 3, 6, 8, 9, 10, 11)
_MODEL_FORMAT = "orbitalpv-pv-forest-v1"


def _optional(module: str) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ImportError(
            "PV footprint methods require the ground extra; install "
            "python -m pip install 'orbital-pv[ground]'."
        ) from exc


def _integer(value: int, name: str, *, minimum: int = 1, maximum: int | None = None) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum or 'unbounded'}")
    return value


def _nonnegative(value: float, name: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return float(value)


def _projected_grid(crs_value: str, transform: Sequence[float]) -> tuple[Any, Any, float]:
    rio = _optional("rasterio")
    if len(transform) != 6 or not all(math.isfinite(value) for value in transform):
        raise ValueError("Image affine must contain six finite coefficients")
    affine = _optional("rasterio.transform").Affine(*transform)
    if affine.a <= 0 or affine.e >= 0 or affine.b != 0 or affine.d != 0:
        raise ValueError("PV detection requires a north-up, unrotated image grid")
    crs = rio.crs.CRS.from_user_input(crs_value)
    if not crs.is_projected:
        raise ValueError("PV detection needs a projected image CRS with linear units")
    _, metres_per_unit = crs.linear_units_factor
    if not math.isfinite(metres_per_unit) or metres_per_unit <= 0:
        raise ValueError("Image CRS must have known positive linear-unit conversion")
    return crs, affine, float(metres_per_unit)


def _actual_bounds(affine: Any, shape: Sequence[int]) -> tuple[float, float, float, float]:
    height, width = shape
    return (affine.c, affine.f + height * affine.e, affine.c + width * affine.a, affine.f)


def _grid(image: GroundImage) -> tuple[Any, Any, float]:
    if image.data.ndim != 3 or image.data.shape[0] != 1 or 0 in image.data.shape:
        raise ValueError("Each spectral/SCL asset must contain one nonempty image band")
    crs, affine, unit = _projected_grid(image.crs, image.transform)
    actual = _actual_bounds(affine, image.data.shape[1:])
    if len(image.bounds) != 4 or not np.allclose(image.bounds, actual, rtol=0, atol=1e-7):
        raise ValueError("GroundImage bounds disagree with its affine transform and shape")
    return crs, affine, unit


@dataclass(frozen=True, slots=True)
class PVFeatures:
    """Derived spectral predictors and validity on one projected image grid.

    ``data`` has shape ``(rows, columns, features)``. ``valid_mask=True``
    means all predictors and the requested SCL quality filters are usable.
    Grid areas are projected areas, not an individual-module measurement.
    """

    data: np.ndarray
    valid_mask: np.ndarray
    feature_names: tuple[str, ...]
    crs: str
    transform: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]
    bbox_wgs84: tuple[float, float, float, float]
    scene_id: str
    pixel_area_m2: float
    provenance: dict[str, Any]


def build_pv_features(
    images: Mapping[str, GroundImage],
    *,
    excluded_scl: Sequence[int] = DEFAULT_EXCLUDED_SCL,
    max_pixels: int = 4_000_000,
) -> PVFeatures:
    """Calibrate six bands and align them to the native red grid.

    Requires ``blue``, ``green``, ``red``, ``nir``, ``swir16``, ``swir22`` and
    ``scl`` from the same scene and requested area. Reflectance uses each
    source's explicit scale/offset, including negative valid values. Any
    different spectral grid is resampled bilinearly; SCL always uses nearest
    neighbour. No source array or metadata is modified. Upsampled SWIR still
    contains only its original 20 m spatial information.

    The default excludes nodata, defective pixels, topographic/cloud shadow,
    water, cloud/cirrus and snow. This also excludes floating-PV water pixels;
    callers studying such systems must explicitly choose quality classes.
    The NDVI/NDBI/MNDWI denominator must have absolute value above 1e-6.
    """
    _integer(max_pixels, "max_pixels")
    required = (*PV_SPECTRAL_BANDS, "scl")
    if missing := set(required).difference(images):
        raise ValueError(f"Missing PV feature assets: {', '.join(sorted(missing))}")
    if any(
        isinstance(code, bool) or not isinstance(code, int) or code not in range(12)
        for code in excluded_scl
    ):
        raise ValueError("excluded_scl must contain integer SCL codes from 0 to 11")
    reference = images["red"]
    crs, affine, unit = _grid(reference)
    shape = reference.data.shape[1:]
    if math.prod(shape) > max_pixels:
        raise ValueError("Feature grid exceeds max_pixels")
    warp = _optional("rasterio.warp")
    resampling = _optional("rasterio.enums").Resampling
    bands: dict[str, np.ndarray] = {}
    sources: dict[str, Any] = {}
    for name in required:
        image = images[name]
        src_crs, src_affine, _ = _grid(image)
        if image.asset_key != name:
            raise ValueError(f"Asset {name!r} does not match its GroundImage asset_key")
        if image.scene_id != reference.scene_id or image.bbox_wgs84 != reference.bbox_wgs84:
            raise ValueError("All feature assets must describe the same scene and requested area")
        if name == "scl":
            raw = image.data[0]
            valid_values = raw.compressed()
            if np.any(~np.isin(valid_values, np.arange(12))):
                raise ValueError("SCL must contain integer class codes from 0 to 11")
        else:
            raw = image.reflectance()[0]
        source = np.asarray(raw.astype(np.float32).filled(np.nan), dtype=np.float32)
        method = resampling.nearest if name == "scl" else resampling.bilinear
        unchanged = src_crs == crs and src_affine == affine and source.shape == shape
        if unchanged:
            aligned = source.copy()
        else:
            aligned = np.full(shape, np.nan, dtype=np.float32)
            warp.reproject(
                source=source,
                destination=aligned,
                src_transform=src_affine,
                src_crs=src_crs,
                src_nodata=np.nan,
                dst_transform=affine,
                dst_crs=crs,
                dst_nodata=np.nan,
                resampling=method,
            )
        bands[name] = aligned
        sources[name] = {
            "url": image.source_url,
            "scene_id": image.scene_id,
            "native_shape": list(source.shape),
            "native_transform": list(image.transform),
            "resampling": "none" if unchanged else method.name,
        }
    derived = []
    for positive, negative in (("nir", "red"), ("swir16", "nir"), ("green", "swir16")):
        numerator = bands[positive] - bands[negative]
        denominator = bands[positive] + bands[negative]
        ratio = np.full(shape, np.nan, dtype=np.float32)
        np.divide(numerator, denominator, out=ratio, where=np.abs(denominator) > 1e-6)
        derived.append(ratio)
    data = np.stack([*(bands[key] for key in PV_SPECTRAL_BANDS), *derived], axis=-1)
    valid = np.isfinite(data).all(axis=-1) & np.isfinite(bands["scl"])
    valid &= ~np.isin(bands["scl"], excluded_scl)
    bbox = warp.transform_bounds(crs, "EPSG:4326", *reference.bounds, densify_pts=21)
    return PVFeatures(
        data=data,
        valid_mask=valid,
        feature_names=PV_FEATURE_NAMES,
        crs=crs.to_string(),
        transform=reference.transform,
        bounds=reference.bounds,
        bbox_wgs84=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        scene_id=reference.scene_id,
        pixel_area_m2=abs(affine.a * affine.e) * unit**2,
        provenance={
            "method": "calibrated six-band spectral predictors with three normalized differences",
            "sources": sources,
            "reference_asset": "red",
            "excluded_scl": list(excluded_scl),
            "source_pixels_modified": False,
            "upsampling_adds_spatial_information": False,
        },
    )


def _check_features(features: PVFeatures) -> None:
    if (
        features.data.ndim != 3
        or 0 in features.data.shape
        or features.data.shape[:2] != features.valid_mask.shape
        or features.valid_mask.dtype != bool
        or features.data.shape[2] != len(features.feature_names)
        or len(set(features.feature_names)) != len(features.feature_names)
        or not features.feature_names
        or not np.isfinite(features.data[features.valid_mask]).all()
        or not math.isfinite(features.pixel_area_m2)
        or features.pixel_area_m2 <= 0
    ):
        raise ValueError("Invalid feature data, feature names, validity mask or pixel area")
    west, south, east, north = features.bbox_wgs84
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Feature bounding box must be finite, ordered WGS84 coordinates")
    crs, affine, unit = _projected_grid(features.crs, features.transform)
    actual = _actual_bounds(affine, features.valid_mask.shape)
    bbox = _optional("rasterio.warp").transform_bounds(crs, "EPSG:4326", *actual, densify_pts=21)
    pixel_area = abs(affine.a * affine.e) * unit**2
    if (
        len(features.bounds) != 4
        or not np.allclose(features.bounds, actual, rtol=0, atol=1e-7)
        or not np.allclose(features.bbox_wgs84, bbox, rtol=0, atol=1e-8)
        or not math.isclose(features.pixel_area_m2, pixel_area, rel_tol=1e-9)
    ):
        raise ValueError(
            "Feature bounds, geographic bbox and pixel area must match the actual grid"
        )


def rasterize_pv_labels(
    features: PVFeatures,
    positive_geometries: Sequence[Mapping[str, Any]],
    *,
    negative_geometries: Sequence[Mapping[str, Any]] | None = None,
    geometry_crs: str = "EPSG:4326",
    background_is_negative: bool = False,
    boundary_buffer_m: float = 0.0,
) -> np.ndarray:
    """Rasterize supplied labels as 1=PV, 0=non-PV, -1=unknown.

    Inputs are polygon/MultiPolygon GeoJSON geometries or Features. Pixel
    centres determine membership. Invalid polygons are rejected, not silently
    repaired. Invalid feature pixels are always unknown. The outside buffer
    around positive geometries remains unknown; positive interiors are not
    eroded. Explicit overlapping positive/negative polygons are rejected.

    Outside supplied polygons remains unknown by default. Opting into
    ``background_is_negative=True`` treats every other valid pixel as non-PV:
    this is a weak assumption for incomplete OSM inventories, not ground
    truth. Record that choice in ``PVTrainingSample.label_source`` and any
    independent evaluation's ``label_source``.
    """
    _check_features(features)
    buffer_m = _nonnegative(boundary_buffer_m, "boundary_buffer_m")
    if not isinstance(background_is_negative, bool):
        raise ValueError("background_is_negative must be a bool")
    shapely = _optional("shapely")
    geometry = _optional("shapely.geometry")
    warp = _optional("rasterio.warp")
    rio = _optional("rasterio")
    raster = _optional("rasterio.features")
    affine = _optional("rasterio.transform").Affine(*features.transform)
    target_crs = rio.crs.CRS.from_user_input(features.crs)
    _, unit = target_crs.linear_units_factor

    def projected(items: Sequence[Mapping[str, Any]]) -> list[Any]:
        result = []
        for item in items:
            item_geometry = item.get("geometry") if item.get("type") == "Feature" else item
            if not isinstance(item_geometry, Mapping) or item_geometry.get("type") not in {
                "Polygon",
                "MultiPolygon",
            }:
                raise ValueError("Training labels must be Polygon or MultiPolygon geometries")
            polygon = geometry.shape(
                warp.transform_geom(geometry_crs, target_crs, dict(item_geometry))
            )
            if polygon.is_empty or not polygon.is_valid or not np.isfinite(polygon.bounds).all():
                raise ValueError("Training label geometry must be finite, nonempty and valid")
            result.append(polygon)
        return result

    positive = shapely.union_all(projected(positive_geometries))
    negative = shapely.union_all(projected(negative_geometries or []))
    if not positive.is_empty and not negative.is_empty and positive.intersection(negative).area > 0:
        raise ValueError("Positive and negative label geometries overlap")
    shape = features.valid_mask.shape

    def burn(polygon: Any) -> np.ndarray:
        if polygon.is_empty:
            return np.zeros(shape, dtype=bool)
        return raster.rasterize(
            [(geometry.mapping(polygon), 1)],
            out_shape=shape,
            transform=affine,
            all_touched=False,
            fill=0,
            dtype="uint8",
        ).astype(bool)

    labels = np.full(shape, 0 if background_is_negative else -1, dtype=np.int8)
    labels[burn(negative)] = 0
    if not positive.is_empty:
        if buffer_m:
            labels[burn(positive.buffer(buffer_m / unit))] = -1
        labels[burn(positive)] = 1
    labels[~features.valid_mask] = -1
    return labels


def _labels(labels: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    values = np.ma.asarray(labels)
    if (
        values.shape != shape
        or values.dtype.kind not in "biu"
        or not np.isin(values.compressed(), (-1, 0, 1)).all()
    ):
        raise ValueError("Labels must match the grid and contain only -1=unknown, 0=non-PV, 1=PV")
    return np.ma.filled(values.astype(np.int8), -1)


@dataclass(frozen=True, slots=True)
class PVTrainingSample:
    """One labelled scene, with a stable site ID and explicit label source."""

    features: PVFeatures
    labels: np.ndarray
    site_id: str
    label_source: str


@dataclass(frozen=True, slots=True)
class PVFootprintPrediction:
    """Image-derived scores, filtered mask and WGS84 footprint polygons.

    ``probabilities`` are uncalibrated forest scores before area filtering.
    ``mask`` retains only thresholded connected components meeting the area
    limit. Both arrays mask invalid pixels rather than coding them non-PV.
    GeoJSON contains grid-derived footprint area, not module surface area.
    """

    probabilities: np.ma.MaskedArray
    mask: np.ma.MaskedArray
    geojson: dict[str, Any]
    metadata: dict[str, Any]

    @property
    def area_m2(self) -> float:
        """Sum of retained projected-grid footprint areas."""
        return sum(feature["properties"]["area_m2"] for feature in self.geojson["features"])


def _boxes_overlap(a: Sequence[float], b: Sequence[float]) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


@dataclass(frozen=True, slots=True)
class PVFootprintModel:
    """An explicitly trained spectral random forest with safe JSON persistence.

    Fitting uses scikit-learn. Prediction reads only learned numeric decision
    trees and the supplied spectral stack; it never queries or consults OSM.
    JSON persistence stores numeric arrays instead of executable pickle data.
    Training provenance is retained so spatially overlapping evaluation can
    be rejected. Held-out-site metrics assess a supplied reference, not
    automatic worldwide validity of the model.
    """

    feature_names: tuple[str, ...]
    trees: tuple[dict[str, list[Any]], ...]
    metadata: dict[str, Any]

    @classmethod
    def fit(
        cls,
        samples: Sequence[PVTrainingSample],
        *,
        random_state: int = 0,
        max_samples_per_class: int = 5_000,
        n_estimators: int = 100,
        min_samples_leaf: int = 3,
        max_depth: int = 20,
    ) -> PVFootprintModel:
        """Fit a deterministic forest from caller-labelled scenes.

        At most ``max_samples_per_class`` valid pixels of each class are
        sampled without replacement from each scene. Random seed, counts,
        site IDs, bounding boxes, scenes and label sources are recorded.
        Class weighting balances the retained training labels. This function
        performs no random-pixel train/test split: such a split cannot test
        transfer to an unseen farm.
        """
        if not samples:
            raise ValueError("At least one labelled training sample is required")
        _integer(random_state, "random_state", minimum=0, maximum=2**32 - 1)
        _integer(max_samples_per_class, "max_samples_per_class")
        _integer(n_estimators, "n_estimators", maximum=2_000)
        _integer(min_samples_leaf, "min_samples_leaf")
        _integer(max_depth, "max_depth", maximum=100)
        rng = np.random.default_rng(random_state)
        x_parts, y_parts, records = [], [], []
        names = samples[0].features.feature_names
        for sample in samples:
            _check_features(sample.features)
            if sample.features.feature_names != names:
                raise ValueError("All training samples must use identical ordered features")
            if not isinstance(sample.site_id, str) or not sample.site_id.strip():
                raise ValueError("Each training sample requires a nonempty site_id")
            if not isinstance(sample.label_source, str) or not sample.label_source.strip():
                raise ValueError("Each training sample requires a nonempty label_source")
            labels = _labels(sample.labels, sample.features.valid_mask.shape)
            counts = {}
            for value in (0, 1):
                candidates = np.flatnonzero(
                    sample.features.valid_mask.ravel() & (labels.ravel() == value)
                )
                if len(candidates) > max_samples_per_class:
                    candidates = rng.choice(candidates, max_samples_per_class, replace=False)
                counts[str(value)] = len(candidates)
                if len(candidates):
                    x_parts.append(sample.features.data.reshape(-1, len(names))[candidates])
                    y_parts.append(np.full(len(candidates), value, dtype=np.uint8))
            records.append(
                {
                    "site_id": sample.site_id,
                    "scene_id": sample.features.scene_id,
                    "bbox_wgs84": list(sample.features.bbox_wgs84),
                    "crs": sample.features.crs,
                    "transform": list(sample.features.transform),
                    "shape": list(sample.features.valid_mask.shape),
                    "label_source": sample.label_source,
                    "selected_pixels": counts,
                }
            )
        if not y_parts or len(np.unique(np.concatenate(y_parts))) != 2:
            raise ValueError("Training requires both PV and non-PV labelled valid pixels")
        ensemble = _optional("sklearn.ensemble")
        classifier = ensemble.RandomForestClassifier(
            n_estimators=n_estimators,
            min_samples_leaf=min_samples_leaf,
            max_depth=max_depth,
            random_state=random_state,
            class_weight="balanced",
            n_jobs=1,
        )
        classifier.fit(np.concatenate(x_parts), np.concatenate(y_parts))
        trees = []
        positive_index = list(classifier.classes_).index(1)
        for estimator in classifier.estimators_:
            tree = estimator.tree_
            counts = tree.value[:, 0, :]
            probabilities = counts[:, positive_index] / counts.sum(axis=1)
            trees.append(
                {
                    "left": tree.children_left.tolist(),
                    "right": tree.children_right.tolist(),
                    "feature": tree.feature.tolist(),
                    "threshold": tree.threshold.tolist(),
                    "probability": probabilities.tolist(),
                }
            )
        return cls(
            feature_names=names,
            trees=tuple(trees),
            metadata={
                "algorithm": "RandomForestClassifier",
                "sklearn_version": _optional("sklearn").__version__,
                "random_state": random_state,
                "n_estimators": n_estimators,
                "min_samples_leaf": min_samples_leaf,
                "max_depth": max_depth,
                "max_samples_per_class_per_scene": max_samples_per_class,
                "class_weight": "balanced",
                "training": records,
                "probabilities_calibrated": False,
                "inference_uses_osm": False,
            },
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "format": _MODEL_FORMAT,
            "feature_names": list(self.feature_names),
            "trees": list(self.trees),
            "metadata": self.metadata,
        }

    @property
    def model_id(self) -> str:
        """SHA-256 of the model's canonical numeric JSON representation."""
        encoded = json.dumps(
            self._payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return sha256(encoded.encode()).hexdigest()

    def save(self, path: str | Path, *, overwrite: bool = False) -> Path:
        """Save non-executable JSON, refusing to overwrite by default."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w" if overwrite else "x", encoding="utf-8") as stream:
            json.dump(
                self._payload(), stream, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            stream.write("\n")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> PVFootprintModel:
        """Read and validate numeric JSON; never execute serialized Python."""
        source = Path(path)
        if source.stat().st_size > 100_000_000:
            raise ValueError("Model JSON exceeds the 100 MB size limit")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            # Python's decoder permits NaN/Infinity, but portable model JSON does not.
            json.dumps(payload, allow_nan=False)
            if not isinstance(payload, dict) or payload.get("format") != _MODEL_FORMAT:
                raise ValueError("Unsupported PV model format")
            names, trees, metadata = payload["feature_names"], payload["trees"], payload["metadata"]
            if (
                not isinstance(names, list)
                or not names
                or not all(isinstance(name, str) and name for name in names)
                or len(set(names)) != len(names)
            ):
                raise ValueError("Invalid model feature names")
            if (
                not isinstance(trees, list)
                or not 1 <= len(trees) <= 2_000
                or not isinstance(metadata, dict)
            ):
                raise ValueError("Invalid model trees or metadata")
            total_nodes = 0
            for tree in trees:
                keys = ("left", "right", "feature", "threshold", "probability")
                if not isinstance(tree, dict) or any(
                    not isinstance(tree.get(key), list) for key in keys
                ):
                    raise ValueError("Invalid numeric decision tree")
                n = len(tree["left"])
                total_nodes += n
                if not n or total_nodes > 2_000_000 or any(len(tree[key]) != n for key in keys):
                    raise ValueError("Invalid tree lengths or too many nodes")
                indegree = np.zeros(n, dtype=np.int32)
                for index, (left, right, feature, threshold, probability) in enumerate(
                    zip(*(tree[key] for key in keys), strict=True)
                ):
                    if any(
                        isinstance(value, bool) or not isinstance(value, int)
                        for value in (left, right, feature)
                    ):
                        raise ValueError("Tree indices must be integers")
                    if (
                        not math.isfinite(threshold)
                        or not math.isfinite(probability)
                        or not 0 <= probability <= 1
                    ):
                        raise ValueError("Invalid tree threshold or probability")
                    if left == right == -1:
                        continue
                    if not (
                        index < left < n
                        and index < right < n
                        and left != right
                        and 0 <= feature < len(names)
                    ):
                        raise ValueError("Invalid or cyclic tree children")
                    indegree[left] += 1
                    indegree[right] += 1
                if indegree[0] != 0 or not np.all(indegree[1:] == 1):
                    raise ValueError("Decision tree must be connected and have one parent per node")
            training = metadata.get("training")
            if not isinstance(training, list) or not training:
                raise ValueError("Model must retain training provenance")
            for record in training:
                if not isinstance(record, dict) or not all(
                    isinstance(record.get(key), str) and record[key]
                    for key in ("site_id", "scene_id", "label_source")
                ):
                    raise ValueError("Invalid training provenance")
                bbox = record.get("bbox_wgs84")
                if (
                    not isinstance(bbox, list)
                    or len(bbox) != 4
                    or not all(math.isfinite(v) for v in bbox)
                    or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90)
                ):
                    raise ValueError("Invalid training bounding box")
                shape = record.get("shape")
                if (
                    not isinstance(shape, list)
                    or len(shape) != 2
                    or any(
                        isinstance(value, bool) or not isinstance(value, int) or value <= 0
                        for value in shape
                    )
                ):
                    raise ValueError("Invalid training grid shape")
                crs, affine, _ = _projected_grid(record["crs"], record["transform"])
                bounds = _actual_bounds(affine, shape)
                actual_bbox = _optional("rasterio.warp").transform_bounds(
                    crs, "EPSG:4326", *bounds, densify_pts=21
                )
                if not np.allclose(bbox, actual_bbox, rtol=0, atol=1e-8):
                    raise ValueError("Training bbox must match its recorded image grid")
            return cls(tuple(names), tuple(trees), metadata)
        except (KeyError, TypeError, json.JSONDecodeError, OverflowError) as exc:
            raise ValueError("Invalid PV model JSON") from exc

    def _scores(self, data: np.ndarray) -> np.ndarray:
        # Match scikit-learn's tree inference conversion before comparison.
        data = np.asarray(data, dtype=np.float32)
        scores = np.zeros(len(data), dtype=np.float64)
        for tree in self.trees:
            left = np.asarray(tree["left"], dtype=np.int32)
            right = np.asarray(tree["right"], dtype=np.int32)
            feature = np.asarray(tree["feature"], dtype=np.int32)
            threshold = np.asarray(tree["threshold"], dtype=np.float64)
            probabilities = np.asarray(tree["probability"], dtype=np.float64)
            nodes = np.zeros(len(data), dtype=np.int32)
            for _ in range(len(left)):
                active = np.flatnonzero(left[nodes] != -1)
                if not len(active):
                    break
                branch = nodes[active]
                take_left = data[active, feature[branch]] <= threshold[branch]
                nodes[active] = np.where(take_left, left[branch], right[branch])
            scores += probabilities[nodes]
        return (scores / len(self.trees)).astype(np.float32)

    def predict(
        self,
        features: PVFeatures,
        *,
        threshold: float = 0.5,
        min_area_m2: float = 1_000.0,
    ) -> PVFootprintPrediction:
        """Infer PV scores and four-connected footprint polygons from imagery.

        No OSM input is accepted. Area filtering removes entire components,
        retaining holes and the red grid's pixel edges. GeoJSON is WGS84;
        areas are measured on the projected input grid. This is approximate
        array footprint area, not panel surface area or installed capacity.
        """
        _check_features(features)
        if features.feature_names != self.feature_names:
            raise ValueError("Prediction feature names/order do not match the trained model")
        if isinstance(threshold, bool) or not math.isfinite(threshold) or not 0 < threshold < 1:
            raise ValueError("threshold must be finite and strictly between 0 and 1")
        minimum = _nonnegative(min_area_m2, "min_area_m2")
        valid = features.valid_mask
        scores = np.full(valid.shape, np.nan, dtype=np.float32)
        flat_valid = np.flatnonzero(valid.ravel())
        flat_data = features.data.reshape(-1, len(self.feature_names))
        for start in range(0, len(flat_valid), 100_000):
            indices = flat_valid[start : start + 100_000]
            scores.ravel()[indices] = self._scores(flat_data[indices])
        candidate = valid & (scores >= threshold)
        raster = _optional("rasterio.features")
        affine = _optional("rasterio.transform").Affine(*features.transform)
        warp = _optional("rasterio.warp")
        geometry = _optional("shapely.geometry")
        polygons, native_polygons = [], []
        pixel_area_units = abs(affine.a * affine.e)
        for index, (polygon, _) in enumerate(
            raster.shapes(
                candidate.astype(np.uint8), mask=candidate, connectivity=4, transform=affine
            )
        ):
            area = geometry.shape(polygon).area / pixel_area_units * features.pixel_area_m2
            if area + features.pixel_area_m2 * 1e-9 < minimum:
                continue
            native_polygons.append((polygon, 1))
            polygons.append(
                {
                    "type": "Feature",
                    "id": index,
                    "geometry": warp.transform_geom(features.crs, "EPSG:4326", polygon),
                    "properties": {
                        "area_m2": float(area),
                        "pixel_count": round(area / features.pixel_area_m2),
                        "source": "image-derived supervised PV candidate",
                        "scene_id": features.scene_id,
                        "threshold": threshold,
                    },
                }
            )
        retained = np.zeros(valid.shape, dtype=bool)
        if native_polygons:
            retained = raster.rasterize(
                native_polygons, out_shape=valid.shape, transform=affine, fill=0, dtype="uint8"
            ).astype(bool)
        overlaps = any(
            _boxes_overlap(features.bbox_wgs84, record["bbox_wgs84"])
            for record in self.metadata["training"]
        )
        metadata = {
            "model_id": self.model_id,
            "scene_id": features.scene_id,
            "crs": features.crs,
            "transform": list(features.transform),
            "bounds": list(features.bounds),
            "bbox_wgs84": list(features.bbox_wgs84),
            "pixel_area_m2": features.pixel_area_m2,
            "inference_uses_osm": False,
            "scores_calibrated": False,
            "threshold": threshold,
            "min_area_m2": minimum,
            "connectivity": 4,
            "valid_pixels": int(valid.sum()),
            "total_pixels": int(valid.size),
            "candidate_pixels_before_area_filter": int(candidate.sum()),
            "retained_pixels": int(retained.sum()),
            "overlaps_training_area": overlaps,
            "area_semantics": "projected pixel footprint; not module surface area",
            "feature_provenance": features.provenance,
        }
        geojson = {"type": "FeatureCollection", "features": polygons, "properties": metadata}
        return PVFootprintPrediction(
            np.ma.array(scores, mask=~valid), np.ma.array(retained, mask=~valid), geojson, metadata
        )

    def evaluate(
        self,
        features: PVFeatures,
        labels: np.ndarray,
        *,
        site_id: str,
        label_source: str,
        threshold: float = 0.5,
        min_area_m2: float = 1_000.0,
    ) -> dict[str, Any]:
        """Evaluate an unseen site against caller-labelled valid pixels.

        Rejects a training site ID or geographic overlap, including a later
        image of the same farm under a different ID. Returns raw-threshold
        and area-filtered metrics separately. OSM labels yield agreement
        with that map snapshot; they do not establish ground-truth accuracy.
        """
        if (
            not isinstance(site_id, str)
            or not site_id.strip()
            or not isinstance(label_source, str)
            or not label_source.strip()
        ):
            raise ValueError("Evaluation requires nonempty site_id and label_source")
        _check_features(features)
        for record in self.metadata["training"]:
            if record["site_id"] == site_id or _boxes_overlap(
                features.bbox_wgs84, record["bbox_wgs84"]
            ):
                raise ValueError(
                    "Held-out evaluation must use a geographically disjoint, unseen site"
                )
        prediction = self.predict(features, threshold=threshold, min_area_m2=min_area_m2)
        raw = np.ma.array(prediction.probabilities >= threshold, mask=~features.valid_mask)
        return {
            "site_id": site_id,
            "scene_id": features.scene_id,
            "label_source": label_source,
            "spatially_disjoint_from_training": True,
            "model_id": self.model_id,
            "threshold": threshold,
            "min_area_m2": min_area_m2,
            "raw_threshold": evaluate_pv_mask(raw, labels),
            "area_filtered": evaluate_pv_mask(prediction.mask, labels),
        }


def evaluate_pv_mask(
    predicted: np.ndarray | np.ma.MaskedArray, labels: np.ndarray
) -> dict[str, Any]:
    """Measure binary agreement on labelled, unmasked pixels only.

    Labels are -1 unknown, 0 non-PV and 1 PV. Unknown labels and masked
    predictions do not become true negatives. Undefined precision/recall/F1/
    IoU are ``None``. Counts and coverage make missing-reference cases clear.
    This low-level scorer does not enforce train/test spatial separation;
    use ``PVFootprintModel.evaluate`` for a held-out-site guard.
    """
    prediction = np.ma.asarray(predicted)
    reference = _labels(labels, prediction.shape)
    if prediction.ndim != 2 or not np.isin(prediction.compressed(), (0, 1)).all():
        raise ValueError("Predictions must be a two-dimensional binary mask")
    usable = ~np.ma.getmaskarray(prediction)
    known = reference != -1
    valid = usable & known
    values = np.asarray(prediction.data, dtype=bool)
    tp = int(np.count_nonzero(valid & values & (reference == 1)))
    fp = int(np.count_nonzero(valid & values & (reference == 0)))
    fn = int(np.count_nonzero(valid & ~values & (reference == 1)))
    tn = int(np.count_nonzero(valid & ~values & (reference == 0)))

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "iou": ratio(tp, tp + fp + fn),
        "accuracy": ratio(tp + tn, tp + fp + fn + tn),
        "evaluated_pixels": int(valid.sum()),
        "labelled_pixels": int(known.sum()),
        "prediction_valid_pixels": int(usable.sum()),
        "total_pixels": int(valid.size),
        "labelled_coverage": ratio(int(valid.sum()), int(known.sum())),
        "evaluated_fraction": ratio(int(valid.sum()), int(valid.size)),
    }
