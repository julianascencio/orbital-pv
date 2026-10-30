"""Reproducible terrestrial PV research with explicit reference and model provenance.

The ANDPI spectral formula and histogram decision rule follow Zeng et al.
(2025), DOI 10.1016/j.jag.2025.105005, and the authors' MIT-licensed
``Fusion_PV_Mapping`` implementation at commit
``ba2f0cd340c57c6780ed63770a9a89b855fde54b``. This module does not silently
substitute a spectral threshold for the paper's prior-inventory fusion pipeline.
Other algorithms are identified as baselines or caller-supplied model adapters.

ANDPI source license (retained here for installed distributions):

MIT License. Copyright (c) 2025 Xiaopeng Zeng.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from space_pv_connectors.ground_research import (
    CopernicusDataSpaceConnector,
    EumetsatConnector,
    GoesABIConnector,
    InventoryAsset,
    PNOAConnector,
    PVInventoryConnector,
    load_pv_inventory,
)

from .pv_detection import (
    PVFeatures,
    PVFootprintModel,
    PVTrainingSample,
    _boxes_overlap,
    _check_features,
    _integer,
    _labels,
    evaluate_pv_mask,
)

ANDPI_SOURCE = {
    "paper_doi": "10.1016/j.jag.2025.105005",
    "code_url": "https://github.com/SUNNYTREE-LAB/Fusion_PV_Mapping/blob/ba2f0cd340c57c6780ed63770a9a89b855fde54b/andpi.py",
    "code_commit": "ba2f0cd340c57c6780ed63770a9a89b855fde54b",
    "code_license": "MIT; see licenses/ANDPI-MIT.txt",
}


def _optional(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ImportError(
            "Install orbital-pv[ground-research] for this ground research method"
        ) from exc


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """Scores and mask on the original feature grid, with invalid pixels masked.

    ``scores`` may be a spectral index or an uncalibrated classifier score;
    its meaning is recorded in ``metadata`` and never assumed probabilistic.
    """

    scores: np.ma.MaskedArray
    mask: np.ma.MaskedArray
    metadata: dict[str, Any]


def andpi_index(bands: PVFeatures | Mapping[str, Any]) -> np.ma.MaskedArray:
    """Return the paper's NDPI spectral index used by adaptive ANDPI.

    Formula: ``(B11 - max(B2, B3, B4, B8, B12)) / (B11 + 1e-10)``.
    Named inputs are calibrated reflectance, on the same grid: blue, green,
    red, nir, swir16 and swir22. Sentinel-2 scale AND offset must already have
    been applied. Negative reflectance is retained, as in the source rule;
    nonfinite and near-zero denominators are masked for numerical safety.
    This spectral score does not resolve module outlines from 10/20 m pixels.
    """
    names = ("blue", "green", "red", "nir", "swir22", "swir16")
    valid: np.ndarray | None = None
    if isinstance(bands, PVFeatures):
        _check_features(bands)
        valid = bands.valid_mask
        arrays = [
            np.ma.asarray(bands.data[..., bands.feature_names.index(name)], dtype=float)
            for name in names
        ]
    else:
        if set(names).difference(bands):
            raise ValueError("ANDPI requires calibrated blue, green, red, nir, swir16 and swir22")
        arrays = [np.ma.asarray(bands[name], dtype=float) for name in names]
    if not arrays or arrays[0].ndim != 2 or 0 in arrays[0].shape:
        raise ValueError("ANDPI bands must be nonempty two-dimensional grids")
    if any(array.shape != arrays[0].shape for array in arrays):
        raise ValueError("ANDPI bands must have identical aligned grids")
    stack = np.ma.stack(arrays)
    data = np.asarray(stack.filled(np.nan), dtype=float)
    mask = np.ma.getmaskarray(stack).any(axis=0) | ~np.isfinite(data).all(axis=0)
    if valid is not None:
        mask |= ~valid
    denominator = data[-1] + 1e-10
    mask |= np.abs(denominator) <= 1e-9
    score = np.full(arrays[0].shape, np.nan)
    np.divide(data[-1] - np.max(data[:-1], axis=0), denominator, out=score, where=~mask)
    return np.ma.array(score, mask=mask)


def adaptive_andpi(
    bands: PVFeatures | Mapping[str, Any],
    *,
    candidate_mask: Any | None = None,
    mode: str = "new",
    retain_ratio: float | None = None,
) -> SegmentationResult:
    """Apply the published ANDPI histogram valley rule to candidate pixels.

    ``mode='new'`` uses positive peaks above 0.02; fewer than two peaks give
    the upstream threshold of 1.0. ``mode='old'`` uses the last two peaks,
    falling back to the candidate mean. The source uses 200 density bins
    over [-0.5, 0.5], height 2, distance 5 and prominence 0.5. With
    ``retain_ratio`` an insufficient retained fraction restores the input
    candidate mask, as in the authors' prior-inventory retention step.

    Omitting a candidate mask applies the rule to the whole usable scene.
    That is an explicitly identified standalone adaptation, not the full
    paper's historical-inventory fusion or a supervised global detector.
    """
    if mode not in {"new", "old"}:
        raise ValueError("mode must be 'new' or 'old'")
    if retain_ratio is not None and (
        isinstance(retain_ratio, bool)
        or not math.isfinite(retain_ratio)
        or not 0 <= retain_ratio <= 1
    ):
        raise ValueError("retain_ratio must be between zero and one")
    score = andpi_index(bands)
    valid = ~np.ma.getmaskarray(score)
    if candidate_mask is None:
        candidates = valid.copy()
    else:
        supplied = np.ma.asarray(candidate_mask)
        if supplied.shape != valid.shape or supplied.dtype.kind != "b":
            raise ValueError("candidate_mask must be a Boolean grid matching the input")
        candidates = supplied.filled(False) & valid
    values = score.data[candidates]
    threshold: float | None = None
    fallback, peaks_at = "empty_candidate_set", []
    detected = np.zeros(valid.shape, dtype=bool)
    if len(values):
        in_range = values[(values >= -0.5) & (values <= 0.5)]
        if len(in_range):
            counts, edges = np.histogram(values, bins=200, density=True, range=(-0.5, 0.5))
            centers = (edges[:-1] + edges[1:]) / 2
            peaks = _optional("scipy.signal").find_peaks(
                counts, height=2, distance=5, prominence=0.5
            )[0]
            peaks = peaks[np.argsort(centers[peaks])]
            if mode == "new":
                peaks = peaks[centers[peaks] > 0.02]
            peaks_at = centers[peaks].tolist()
        else:
            peaks = np.array([], dtype=int)
        if len(peaks) >= 2:
            left, right = (peaks[-3], peaks[-2]) if mode == "new" and len(peaks) > 2 else peaks[-2:]
            start = left + 1
            threshold = float(centers[start + np.argmin(counts[start:right])])
            fallback = "histogram_valley"
        else:
            threshold = 1.0 if mode == "new" else float(np.mean(values))
            fallback = "upstream_new_threshold_1" if mode == "new" else "candidate_mean"
        detected = candidates & (score.data >= threshold)
        if retain_ratio is not None and detected.sum() / len(values) < retain_ratio:
            detected = candidates.copy()
            fallback += "; prior_candidate_retention"
    return SegmentationResult(
        score,
        np.ma.array(detected, mask=~valid),
        {
            "method": "ANDPI adaptive histogram rule",
            "implementation": "candidate refinement"
            if candidate_mask is not None
            else "standalone full-scene adaptation",
            "mode": mode,
            "threshold": threshold,
            "decision": fallback,
            "histogram_peak_centers": peaks_at,
            "candidate_pixels": int(candidates.sum()),
            "retain_ratio": retain_ratio,
            "uses_prior_candidates": candidate_mask is not None,
            "score_kind": "spectral index, not a probability",
            "inferred": True,
            "source": dict(ANDPI_SOURCE),
        },
    )


@dataclass(frozen=True, slots=True)
class SegmentationAdapter:
    """Uniform callable adapter for an explicitly supplied segmentation model.

    The predictor receives ONLY ``PVFeatures`` and returns an aligned score
    grid or ``SegmentationResult``. For PANEL/TransPV the caller loads their
    authorized local checkpoint in its original runtime and passes a
    callable. This class neither recreates their architecture nor downloads
    gated weights. Record training regions and pretraining overlap when known.
    """

    name: str
    predictor: Callable[[PVFeatures], Any] = field(repr=False)
    threshold: float = 0.5
    training: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip() or not callable(self.predictor):
            raise ValueError("A model name and callable predictor are required")
        if not math.isfinite(self.threshold):
            raise ValueError("threshold must be finite")

    @classmethod
    def from_callable(
        cls,
        name: str,
        predictor: Callable[[PVFeatures], Any],
        *,
        weights_path: str | Path | None = None,
        threshold: float = 0.5,
        training: Sequence[Mapping[str, Any]] = (),
        license_name: str,
        implementation: str = "caller-supplied runtime; architecture not implemented by orbitalpv",
        pretraining_overlap: str = "unknown",
    ) -> SegmentationAdapter:
        """Register an external implementation and checksum local weights.

        No pickle/checkpoint is opened by orbitalpv; the caller controls the
        runtime. Supplying a path is provenance, not automatic weight loading.
        """
        if not license_name.strip():
            raise ValueError("Record the supplied model's license explicitly")
        metadata: dict[str, Any] = {
            "implementation": implementation,
            "license": license_name,
            "pretraining_overlap": pretraining_overlap,
            "score_kind": "caller model score; calibration unspecified",
        }
        if weights_path is not None:
            path = Path(weights_path)
            digest = sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            metadata.update(weights_file=path.name, weights_sha256=digest.hexdigest())
        return cls(name, predictor, threshold, tuple(dict(record) for record in training), metadata)

    def predict(self, features: PVFeatures) -> SegmentationResult:
        """Run inference without passing labels and validate the output grid."""
        _check_features(features)
        output = self.predictor(features)
        metadata = dict(self.metadata)
        if isinstance(output, SegmentationResult):
            scores, mask = np.ma.asarray(output.scores), np.ma.asarray(output.mask)
            metadata.update(output.metadata)
            if mask.shape != features.valid_mask.shape or mask.dtype.kind != "b":
                raise ValueError("Model mask must be a matching Boolean grid")
        else:
            scores = np.ma.asarray(output, dtype=float)
            mask = scores >= self.threshold
        if scores.shape != features.valid_mask.shape:
            raise ValueError("Model scores must match the input feature grid")
        valid = features.valid_mask & ~np.ma.getmaskarray(scores) & ~np.ma.getmaskarray(mask)
        if not np.isfinite(scores.data[valid]).all():
            raise ValueError("Model scores must be finite on usable pixels")
        metadata.update(
            model=self.name,
            threshold=self.threshold,
            training=list(self.training),
            scene_id=features.scene_id,
            feature_provenance=features.provenance,
            inference_receives_labels=False,
            inferred=True,
        )
        return SegmentationResult(
            np.ma.array(scores.data, mask=~valid), np.ma.array(mask.data, mask=~valid), metadata
        )


def supervised_segmentation_adapter(
    samples: Sequence[PVTrainingSample],
    *,
    method: str = "logistic",
    random_state: int = 0,
    max_samples_per_class: int = 5_000,
    threshold: float = 0.5,
) -> SegmentationAdapter:
    """Fit balanced logistic regression or the existing spectral random forest.

    Class sampling, scaling and fitting see training scenes only. Logistic
    regression is a useful inexpensive supervised alternative, not a neural
    paper reproduction. The RF uses orbitalpv's persisted numeric-tree model.
    Both report uncalibrated scores and retain geographic training provenance.
    """
    if method not in {"logistic", "random_forest"}:
        raise ValueError("method must be 'logistic' or 'random_forest'")
    if not 0 < threshold < 1:
        raise ValueError("threshold must be strictly between zero and one")
    _integer(random_state, "random_state", minimum=0, maximum=2**32 - 1)
    _integer(max_samples_per_class, "max_samples_per_class")
    if not samples:
        raise ValueError("At least one training scene is required")
    if method == "random_forest":
        model = PVFootprintModel.fit(
            samples, random_state=random_state, max_samples_per_class=max_samples_per_class
        )

        def forest_predict(features: PVFeatures) -> np.ma.MaskedArray:
            return model.predict(features, threshold=threshold, min_area_m2=0).probabilities

        return SegmentationAdapter(
            "spectral_random_forest",
            forest_predict,
            threshold,
            tuple(model.metadata["training"]),
            {
                "implementation": "trained supervised baseline",
                "model_id": model.model_id,
                "score_kind": "uncalibrated forest class score",
            },
        )
    rng = np.random.default_rng(random_state)
    x_parts, y_parts, records = [], [], []
    names = samples[0].features.feature_names
    for sample in samples:
        _check_features(sample.features)
        if (
            sample.features.feature_names != names
            or not sample.site_id.strip()
            or not sample.label_source.strip()
        ):
            raise ValueError(
                "Training requires matching features, nonempty site IDs and label sources"
            )
        labels = _labels(sample.labels, sample.features.valid_mask.shape)
        counts = {}
        for value in (0, 1):
            selected = np.flatnonzero(
                sample.features.valid_mask.ravel() & (labels.ravel() == value)
            )
            if len(selected) > max_samples_per_class:
                selected = rng.choice(selected, max_samples_per_class, replace=False)
            counts[str(value)] = len(selected)
            if len(selected):
                x_parts.append(sample.features.data.reshape(-1, len(names))[selected])
                y_parts.append(np.full(len(selected), value))
        records.append(
            {
                "site_id": sample.site_id,
                "bbox_wgs84": list(sample.features.bbox_wgs84),
                "scene_id": sample.features.scene_id,
                "label_source": sample.label_source,
                "selected_pixels": counts,
            }
        )
    if not y_parts or len(np.unique(np.concatenate(y_parts))) != 2:
        raise ValueError("Both classes need labelled, valid training pixels")
    pipeline = _optional("sklearn.pipeline").make_pipeline(
        _optional("sklearn.preprocessing").StandardScaler(),
        _optional("sklearn.linear_model").LogisticRegression(
            class_weight="balanced", random_state=random_state, max_iter=1_000
        ),
    )
    pipeline.fit(np.concatenate(x_parts), np.concatenate(y_parts))

    def logistic_predict(features: PVFeatures) -> np.ma.MaskedArray:
        if features.feature_names != names:
            raise ValueError("Prediction features differ from the fitted model")
        values = np.full(features.valid_mask.shape, np.nan)
        if features.valid_mask.any():
            values[features.valid_mask] = pipeline.predict_proba(
                features.data[features.valid_mask]
            )[:, 1]
        return np.ma.array(values, mask=~features.valid_mask)

    return SegmentationAdapter(
        "spectral_logistic",
        logistic_predict,
        threshold,
        tuple(records),
        {
            "implementation": "standardized balanced logistic regression baseline",
            "score_kind": "uncalibrated logistic class score",
            "random_state": random_state,
            "sklearn_version": _optional("sklearn").__version__,
        },
    )


def benchmark_segmentation(
    adapters: Sequence[SegmentationAdapter],
    samples: Sequence[PVTrainingSample],
) -> dict[str, Any]:
    """Evaluate geographically held-out scenes on explicitly known labels.

    Rejects training-site reuse and geographic overlap BEFORE inference.
    Unknown labels and invalid pixels are excluded from both area measures.
    Completely labelled false-positive connected objects are counted; objects
    touching unknown support are counted as unevaluable, not false positives.
    Metrics inherit the supplied reference's quality (e.g. OSM weak labels).
    Foundation-model pretraining overlap cannot be inferred from checkpoints.
    """
    if not adapters or not samples:
        raise ValueError("Provide models and held-out labelled scenes")
    if len({model.name for model in adapters}) != len(adapters):
        raise ValueError("Benchmark model names must be unique")
    for model in adapters:
        for sample in samples:
            _check_features(sample.features)
            _labels(sample.labels, sample.features.valid_mask.shape)
            for training in model.training:
                if not training.get("site_id") or "bbox_wgs84" not in training:
                    raise ValueError(
                        "Training provenance needs site_id and bbox_wgs84 for geographic checks"
                    )
                if training["site_id"] == sample.site_id or _boxes_overlap(
                    training["bbox_wgs84"], sample.features.bbox_wgs84
                ):
                    raise ValueError(
                        f"Geographic leakage: {sample.site_id} overlaps training for {model.name}"
                    )
    rows = []
    ndimage = _optional("scipy.ndimage")
    for sample in samples:
        labels = _labels(sample.labels, sample.features.valid_mask.shape)
        for model in adapters:
            prediction = model.predict(sample.features)
            metrics = evaluate_pv_mask(prediction.mask, labels)
            known = (labels >= 0) & ~np.ma.getmaskarray(prediction.mask)
            positive = prediction.mask.filled(False)
            true_pixels = int(np.sum(known & (labels == 1)))
            predicted_pixels = int(np.sum(known & positive))
            area = float(sample.features.pixel_area_m2)
            components, count = ndimage.label(positive)
            false_objects, uncertain_objects = 0, 0
            for component in range(1, count + 1):
                pixels = components == component
                if np.any(pixels & ~known):
                    uncertain_objects += 1
                elif not np.any(pixels & (labels == 1)):
                    false_objects += 1
            negatives = known & (labels == 0)
            fp = int(np.sum(negatives & positive))
            metrics.update(
                site_id=sample.site_id,
                scene_id=sample.features.scene_id,
                model=model.name,
                label_source=sample.label_source,
                evaluated_area_m2=float(known.sum() * area),
                reference_area_m2=true_pixels * area,
                predicted_area_m2=predicted_pixels * area,
                area_bias_m2=(predicted_pixels - true_pixels) * area,
                relative_area_bias=(predicted_pixels - true_pixels) / true_pixels
                if true_pixels
                else None,
                false_positive_rate=fp / int(negatives.sum()) if negatives.any() else None,
                false_positive_objects=false_objects,
                objects_with_unknown_labels=uncertain_objects,
                false_positive_objects_per_km2=false_objects / (known.sum() * area / 1e6)
                if known.any()
                else None,
                prediction_provenance=prediction.metadata,
            )
            rows.append(metrics)
    return {
        "evaluation": "geographic holdout, no tuning on evaluation labels",
        "area_support": "known reference and usable prediction pixels only",
        "label_leakage_check": "site IDs and geographic rectangles; caller must disclose pretraining coverage",
        "reference_status": "caller labels; weak labels are not surveyed ground truth",
        "results": rows,
    }


def _polygon_features(collection: Mapping[str, Any]) -> list[tuple[str, Any, dict[str, Any]]]:
    if collection.get("type") != "FeatureCollection" or "crs" in collection:
        raise ValueError("Require RFC7946 WGS84 GeoJSON FeatureCollection without legacy crs")
    shape = _optional("shapely.geometry").shape
    output, seen = [], set()
    for index, feature in enumerate(collection.get("features", [])):
        identifier = str(feature.get("id", index))
        if identifier in seen:
            raise ValueError("Feature IDs must be unique")
        seen.add(identifier)
        geom = shape(feature["geometry"])
        if geom.geom_type not in {"Polygon", "MultiPolygon"} or geom.is_empty or not geom.is_valid:
            raise ValueError("Require nonempty valid polygon geometries")
        west, south, east, north = geom.bounds
        if (
            not np.isfinite(geom.bounds).all()
            or not (-180 <= west < east <= 180 and -90 <= south < north <= 90)
            or east - west > 180
        ):
            raise ValueError("Require finite WGS84 bounds without antimeridian crossing")
        output.append((identifier, geom, dict(feature.get("properties", {}))))
    return output


def summarize_pv_geometry(collection: Mapping[str, Any]) -> pd.DataFrame:
    """Measure polygon footprint geometry in each feature's local UTM CRS.

    Reports minimum-rectangle long-axis azimuth modulo 180 degrees. This is
    a row/footprint axis, NOT panel facing azimuth or tilt. A farm-boundary
    polygon does not become module surface area. Input attributes, original
    geometry source and the metric CRS are preserved in each output record.
    """
    transform = _optional("shapely").transform
    pyproj = _optional("pyproj")
    rows = []
    for identifier, geometry, properties in _polygon_features(collection):
        lon, lat = geometry.centroid.x, geometry.centroid.y
        if not -80 <= lat <= 84:
            raise ValueError("Local UTM geometry analysis supports latitudes -80 to 84")
        zone = min(60, int((lon + 180) // 6) + 1)
        crs = f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"
        projected = transform(
            geometry,
            pyproj.Transformer.from_crs(4326, crs, always_xy=True).transform,
            interleaved=False,
        )
        coordinates = np.asarray(projected.minimum_rotated_rectangle.exterior.coords)
        deltas = np.diff(coordinates, axis=0)
        lengths = np.linalg.norm(deltas, axis=1)
        index = int(np.argmax(lengths))
        dx, dy = deltas[index]
        rows.append(
            {
                "feature_id": identifier,
                "footprint_area_m2": float(projected.area),
                "long_axis_m": float(lengths.max()),
                "short_axis_m": float(lengths.min()),
                "axis_azimuth_deg": float(math.degrees(math.atan2(dx, dy)) % 180),
                "axis_is_direction_ambiguous": True,
                "panel_tilt_deg": None,
                "metric_crs": crs,
                "status": "geometry-derived, not measured equipment metadata",
                "source_properties": properties,
            }
        )
    return pd.DataFrame(rows)


def _capacity_table(
    frame: pd.DataFrame, names: Sequence[str], *, response: bool
) -> tuple[np.ndarray, np.ndarray | None, tuple[str, ...]]:
    required = {*names, "site_id"} | ({"capacity_mw"} if response else set())
    if required.difference(frame.columns) or frame.empty:
        raise ValueError(f"Capacity table needs nonempty rows and columns {sorted(required)}")
    if frame.site_id.isna().any():
        raise ValueError("Capacity site_id must be nonempty and unique")
    ids = tuple(frame.site_id.astype(str))
    if any(not value.strip() for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Capacity site_id must be nonempty and unique")
    x = frame.loc[:, list(names)].to_numpy(dtype=float, copy=True)
    if not np.isfinite(x).all():
        raise ValueError("Capacity features must be finite")
    for index, name in enumerate(names):
        if name.endswith("_m2"):
            if np.any(x[:, index] <= 0):
                raise ValueError("Area features must be positive")
            x[:, index] = np.log(x[:, index])
    y = frame.capacity_mw.to_numpy(dtype=float) if response else None
    if y is not None and (not np.isfinite(y).all() or np.any(y <= 0)):
        raise ValueError("Reference capacity must be finite and strictly positive")
    return x, y, ids


@dataclass(frozen=True, slots=True)
class GeometryCapacityModel:
    """Log-linear area/geometry regression with separate conformal calibration.

    Calibration uses absolute log residuals and the finite-sample order
    statistic ceil((n+1)*coverage). Coverage requires exchangeability; a
    held-out country's observed coverage is reported rather than guaranteed.
    AC/DC/reported and polygon-area semantics must match the calibration.
    """

    feature_names: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    residual_quantile: float
    coverage: float
    capacity_basis: str
    area_basis: str
    feature_min: tuple[float, ...]
    feature_max: tuple[float, ...]
    training_ids: tuple[str, ...]
    calibration_ids: tuple[str, ...]
    provenance: dict[str, Any]

    def predict(
        self,
        frame: pd.DataFrame,
        *,
        area_basis: str,
        output_basis: str | None = None,
        dc_ac_ratio: float | None = None,
        allow_extrapolation: bool = False,
    ) -> pd.DataFrame:
        """Predict median-like MW and calibrated intervals; refuse unseen feature ranges by default.

        Converting AC/DC requires an explicit DC/AC ratio and is labelled an
        assumption. An unspecified ``reported`` basis cannot be converted.
        The ratio's own uncertainty is not represented by these intervals.
        """
        if area_basis != self.area_basis:
            raise ValueError("area_basis must match calibration semantics")
        x, _, ids = _capacity_table(frame, self.feature_names, response=False)
        outside = ((x < np.array(self.feature_min)) | (x > np.array(self.feature_max))).any(axis=1)
        if outside.any() and not allow_extrapolation:
            raise ValueError(
                "Prediction extrapolates beyond training feature ranges; explicitly opt in"
            )
        target = output_basis or self.capacity_basis
        if target not in {"AC", "DC", "reported"}:
            raise ValueError("output_basis must be AC, DC or reported")
        factor = 1.0
        if target != self.capacity_basis:
            if {target, self.capacity_basis} != {"AC", "DC"}:
                raise ValueError("Unspecified reported capacity cannot be relabelled AC or DC")
            if (
                dc_ac_ratio is None
                or isinstance(dc_ac_ratio, bool)
                or not math.isfinite(dc_ac_ratio)
                or dc_ac_ratio <= 0
            ):
                raise ValueError("AC/DC conversion needs an explicit finite positive dc_ac_ratio")
            factor = dc_ac_ratio if target == "DC" else 1 / dc_ac_ratio
        elif dc_ac_ratio is not None:
            raise ValueError("dc_ac_ratio is only used for an explicit AC/DC conversion")
        location = (x - self.mean) / self.scale @ np.array(self.coefficients) + self.intercept
        with np.errstate(over="raise"):
            try:
                point = np.exp(location) * factor
                lower = np.exp(location - self.residual_quantile) * factor
                upper = np.exp(location + self.residual_quantile) * factor
            except FloatingPointError as exc:
                raise ValueError(
                    "Capacity prediction overflow; inspect feature units and extrapolation"
                ) from exc
        result = pd.DataFrame(
            {
                "site_id": ids,
                "capacity_mw": point,
                "lower_mw": lower,
                "upper_mw": upper,
                "coverage_nominal": self.coverage,
                "capacity_basis": target,
                "extrapolated": outside,
                "inferred": True,
                "conversion_assumption": "none"
                if target == self.capacity_basis
                else f"DC/AC={dc_ac_ratio}; ratio uncertainty omitted",
            }
        )
        result.attrs.update(
            model_provenance=self.provenance,
            area_basis=area_basis,
            interval_method="split conformal absolute log residual",
            coverage_assumption="exchangeable calibration and prediction sites",
        )
        return result


def fit_geometry_capacity_model(
    training: pd.DataFrame,
    calibration: pd.DataFrame,
    *,
    feature_names: Sequence[str] = ("footprint_area_m2",),
    capacity_basis: str,
    area_basis: str,
    source: str,
    coverage: float = 0.9,
    ridge: float = 1e-6,
    group_column: str | None = None,
) -> GeometryCapacityModel:
    """Fit on training sites and calibrate on disjoint sites/groups only.

    Tables contain stable ``site_id``, positive ``capacity_mw`` and the
    selected predictors. Area columns ending ``_m2`` are log transformed;
    other geometry predictors stay linear. Never select features or tune
    thresholds on the calibration or final test set. ``group_column`` also
    rejects reused countries/regions across fitting and calibration.
    """
    names = tuple(feature_names)
    if not names or len(set(names)) != len(names):
        raise ValueError("Provide unique feature names")
    if {"capacity_mw", "site_id"}.intersection(names):
        raise ValueError("Reference capacity and site identity cannot be predictive features")
    if (
        capacity_basis not in {"AC", "DC", "reported"}
        or not area_basis.strip()
        or not source.strip()
    ):
        raise ValueError(
            "Explicit AC/DC/reported capacity basis, area basis and source are required"
        )
    if not math.isfinite(coverage) or not 0 < coverage < 1 or not math.isfinite(ridge) or ridge < 0:
        raise ValueError("coverage must be in (0,1) and ridge nonnegative")
    x, y, training_ids = _capacity_table(training, names, response=True)
    xc, yc, calibration_ids = _capacity_table(calibration, names, response=True)
    if set(training_ids) & set(calibration_ids):
        raise ValueError("Training and calibration sites must be disjoint")
    if len(x) < len(names) + 2:
        raise ValueError("Too few training sites for the selected geometry predictors")
    groups: dict[str, Any] = {}
    if group_column is not None:
        if group_column not in training or group_column not in calibration:
            raise ValueError("group_column must be present in both data tables")
        if training[group_column].isna().any() or calibration[group_column].isna().any():
            raise ValueError("Geographic groups cannot be missing")
        train_groups = set(training[group_column].astype(str))
        cal_groups = set(calibration[group_column].astype(str))
        if any(not value.strip() for value in train_groups | cal_groups):
            raise ValueError("Geographic groups cannot be blank")
        if train_groups & cal_groups:
            raise ValueError("Training and calibration geographic groups must be disjoint")
        groups = {
            "column": group_column,
            "training": sorted(train_groups),
            "calibration": sorted(cal_groups),
        }
    rank = math.ceil((len(xc) + 1) * coverage)
    if rank > len(xc):
        raise ValueError(
            "Too few independent calibration sites for a finite interval at this coverage"
        )
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale <= 1e-12] = 1.0
    standardized = (x - mean) / scale
    assert y is not None and yc is not None
    intercept = float(np.log(y).mean())
    coefficients = np.linalg.lstsq(
        np.vstack((standardized, math.sqrt(ridge) * np.eye(len(names)))),
        np.r_[np.log(y) - intercept, np.zeros(len(names))],
        rcond=None,
    )[0]
    residuals = np.abs(np.log(yc) - ((xc - mean) / scale @ coefficients + intercept))
    quantile = float(np.sort(residuals)[rank - 1])
    return GeometryCapacityModel(
        names,
        tuple(mean),
        tuple(scale),
        tuple(coefficients),
        intercept,
        quantile,
        float(coverage),
        capacity_basis,
        area_basis,
        tuple(x.min(axis=0)),
        tuple(x.max(axis=0)),
        training_ids,
        calibration_ids,
        {
            "source": source,
            "capacity_basis": capacity_basis,
            "area_basis": area_basis,
            "method": "log-linear ridge baseline with split-conformal calibration",
            "ridge": ridge,
            "calibration_sites": len(xc),
            "calibration_order_statistic": rank,
            "groups": groups,
            "site_independence": "caller stable site IDs; nearby sites may remain dependent",
            "inferred": True,
            "coverage_is_guaranteed_under_geographic_shift": False,
        },
    )


def evaluate_geometry_capacity(
    model: GeometryCapacityModel, reference: pd.DataFrame
) -> dict[str, Any]:
    """Score untouched sites with empirical coverage, error and interval width."""
    _, measured, ids = _capacity_table(reference, model.feature_names, response=True)
    if set(ids) & (set(model.training_ids) | set(model.calibration_ids)):
        raise ValueError("Final test sites must be disjoint from fitting and calibration")
    groups = model.provenance.get("groups", {})
    if groups:
        column = groups["column"]
        if column not in reference:
            raise ValueError("Final test requires the geographic group column")
        if reference[column].isna().any() or any(
            not value.strip() for value in reference[column].astype(str)
        ):
            raise ValueError("Final test geographic groups cannot be missing or blank")
        if set(reference[column].astype(str)) & (
            set(groups["training"]) | set(groups["calibration"])
        ):
            raise ValueError("Final test geographic groups overlap fitting or calibration")
    prediction = model.predict(reference, area_basis=model.area_basis, allow_extrapolation=True)
    assert measured is not None
    errors = prediction.capacity_mw.to_numpy() - measured
    ss = float(np.sum((measured - measured.mean()) ** 2))
    return {
        "n": len(reference),
        "capacity_basis": model.capacity_basis,
        "mae_mw": float(np.abs(errors).mean()),
        "rmse_mw": float(np.sqrt(np.mean(errors**2))),
        "bias_mw": float(errors.mean()),
        "r_squared": 1 - float(np.sum(errors**2)) / ss if ss else None,
        "coverage_nominal": model.coverage,
        "coverage_observed": float(
            ((measured >= prediction.lower_mw) & (measured <= prediction.upper_mw)).mean()
        ),
        "mean_interval_width_mw": float((prediction.upper_mw - prediction.lower_mw).mean()),
        "extrapolated_sites": int(prediction.extrapolated.sum()),
        "inferred_vs_measured": "inferred MW versus caller reference capacity",
        "model_provenance": model.provenance,
    }


def match_pv_changes(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    before_time: str,
    after_time: str,
    complete_coverage: bool = False,
    min_overlap: float = 0.1,
    relative_area_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Match two dated inventories, grouping polygon splits and merges.

    Links require intersection/minimum(area) >= ``min_overlap``. Connected
    bipartite groups avoid treating a split as construction. Areas use an
    equal-area projection. Added/removed interpretations require an explicit
    assertion that BOTH snapshots completely survey the same footprint.
    Otherwise report newly observed/not redetected. Detection date brackets
    never assert commissioning or an exact construction date.
    """
    t0, t1 = pd.Timestamp(before_time), pd.Timestamp(after_time)
    t0 = t0.tz_localize("UTC") if t0.tz is None else t0.tz_convert("UTC")
    t1 = t1.tz_localize("UTC") if t1.tz is None else t1.tz_convert("UTC")
    if pd.isna(t0) or pd.isna(t1) or t0 >= t1:
        raise ValueError("Require distinct chronological observation times")
    if not 0 < min_overlap <= 1 or not 0 <= relative_area_tolerance < 1:
        raise ValueError("Invalid overlap or area tolerance")
    old, new = _polygon_features(before), _polygon_features(after)
    transform = _optional("shapely").transform
    transformer = _optional("pyproj").Transformer.from_crs(4326, 6933, always_xy=True)
    old_geom = [transform(entry[1], transformer.transform, interleaved=False) for entry in old]
    new_geom = [transform(entry[1], transformer.transform, interleaved=False) for entry in new]
    all_geom = old_geom + new_geom
    parents = list(range(len(all_geom)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    if new_geom:
        tree = _optional("shapely").STRtree(new_geom)
        for i, polygon in enumerate(old_geom):
            for j in tree.query(polygon, predicate="intersects"):
                candidate = new_geom[j]
                if (
                    polygon.intersection(candidate).area / min(polygon.area, candidate.area)
                    >= min_overlap
                ):
                    parents[root(i)] = root(len(old) + int(j))
    groups: dict[int, list[int]] = {}
    for i in range(len(all_geom)):
        groups.setdefault(root(i), []).append(i)
    union_all = _optional("shapely").union_all
    rows = []
    for indices in groups.values():
        old_indices = [i for i in indices if i < len(old)]
        new_indices = [i - len(old) for i in indices if i >= len(old)]
        old_union, new_union = (
            union_all([old_geom[i] for i in old_indices]),
            union_all([new_geom[i] for i in new_indices]),
        )
        area0, area1 = float(old_union.area), float(new_union.area)
        if not old_indices:
            status = "added_between_observations" if complete_coverage else "newly_observed"
        elif not new_indices:
            status = "removed_between_observations" if complete_coverage else "not_redetected"
        elif area1 > area0 * (1 + relative_area_tolerance):
            status = "expanded_footprint"
        elif area1 < area0 * (1 - relative_area_tolerance):
            status = "contracted_footprint"
        else:
            status = "persistent_footprint"
        total = old_union.union(new_union).area
        rows.append(
            {
                "before_ids": [old[i][0] for i in old_indices],
                "after_ids": [new[i][0] for i in new_indices],
                "status": status,
                "area_before_m2": area0,
                "area_after_m2": area1,
                "area_change_m2": area1 - area0,
                "group_iou": float(old_union.intersection(new_union).area / total)
                if total
                else None,
                "split_or_merge": bool(
                    old_indices and new_indices and (len(old_indices) > 1 or len(new_indices) > 1)
                ),
                "change_window_start_exclusive": t0.isoformat()
                if complete_coverage and status != "persistent_footprint"
                else None,
                "change_window_end_inclusive": t1.isoformat()
                if complete_coverage and status != "persistent_footprint"
                else None,
                "before_properties": [old[i][2] for i in old_indices],
                "after_properties": [new[i][2] for i in new_indices],
            }
        )
    return {
        "observations": [t0.isoformat(), t1.isoformat()],
        "complete_shared_coverage_asserted": complete_coverage,
        "method": "overlap graph with split/merge grouping; EPSG:6933 area",
        "min_overlap": min_overlap,
        "relative_area_tolerance": relative_area_tolerance,
        "date_semantics": "observed footprint change bracket; not electrical commissioning",
        "inferred": True,
        "source_before": before.get("metadata", before.get("properties", {})),
        "source_after": after.get("metadata", after.get("properties", {})),
        "changes": rows,
    }


__all__ = [
    "ANDPI_SOURCE",
    "CopernicusDataSpaceConnector",
    "EumetsatConnector",
    "GeometryCapacityModel",
    "GoesABIConnector",
    "InventoryAsset",
    "PNOAConnector",
    "PVInventoryConnector",
    "SegmentationAdapter",
    "SegmentationResult",
    "adaptive_andpi",
    "andpi_index",
    "benchmark_segmentation",
    "evaluate_geometry_capacity",
    "fit_geometry_capacity_model",
    "load_pv_inventory",
    "match_pv_changes",
    "summarize_pv_geometry",
    "supervised_segmentation_adapter",
]
