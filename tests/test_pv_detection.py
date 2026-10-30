"""Geospatial and held-out checks for the image-derived PV baseline."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from space_pv_connectors.ground_raster import GroundImage

pytest.importorskip("rasterio")
pytest.importorskip("shapely")
pytest.importorskip("sklearn")

from orbitalpv.pv_detection import (
    DEFAULT_EXCLUDED_SCL,
    PV_FEATURE_NAMES,
    PV_SPECTRAL_BANDS,
    PVFeatures,
    PVFootprintModel,
    PVTrainingSample,
    build_pv_features,
    evaluate_pv_mask,
    rasterize_pv_labels,
)


def _image(name, values, *, resolution=10, crs="EPSG:32628", left=350000):
    data = np.ma.array(values, dtype=np.float64)
    if data.ndim == 2:
        data = data[None, :, :]
    height, width = data.shape[1:]
    metadata = {"roles": ["data"]}
    if name != "scl":
        metadata = {
            "roles": ["data", "reflectance"],
            "raster:bands": [{"scale": 0.0001, "offset": -0.1}],
        }
    return GroundImage(
        data=data,
        crs=crs,
        transform=(resolution, 0, left, 0, -resolution, 3120000),
        bounds=(left, 3120000 - resolution * height, left + resolution * width, 3120000),
        scene_id="scene",
        asset_key=name,
        source_url=f"https://example.org/{name}.tif",
        asset_metadata=metadata,
        bbox_wgs84=(-16.5, 28.0, -16.4, 28.1),
        item_metadata={"id": "scene"},
        nodata_values=(0,),
        retrieved_at="2026-10-30T00:00:00Z",
    )


def _images():
    images = {
        name: _image(name, np.full((10, 10), 2000 + 100 * index))
        for index, name in enumerate(PV_SPECTRAL_BANDS)
    }
    images["swir16"] = _image("swir16", np.full((5, 5), 2400), resolution=20)
    images["swir22"] = _image("swir22", np.full((5, 5), 2500), resolution=20)
    images["scl"] = _image("scl", np.full((5, 5), 5), resolution=20)
    return images


def _features(values, *, bbox=(0.0, 0.0, 0.01, 0.01), scene="test"):
    from rasterio.warp import transform_bounds

    data = np.asarray(values, dtype=np.float32)
    if data.ndim == 2:
        data = data[:, :, None]
    height, width = data.shape[:2]
    # The arguments select actual different projected locations, rather than
    # changing only the metadata used by the held-out guard.
    left, top = 350000 + bbox[0] * 1000, 3120000 + bbox[1] * 1000
    bounds = (left, top - height * 10, left + width * 10, top)
    actual_bbox = transform_bounds("EPSG:32628", "EPSG:4326", *bounds, densify_pts=21)
    return PVFeatures(
        data=data,
        valid_mask=np.ones((height, width), dtype=bool),
        feature_names=tuple(f"feature_{i}" for i in range(data.shape[2])),
        crs="EPSG:32628",
        transform=(10, 0, left, 0, -10, top),
        bounds=bounds,
        bbox_wgs84=actual_bbox,
        scene_id=scene,
        pixel_area_m2=100.0,
        provenance={"test": "known synthetic pixels"},
    )


def _polygon(x1, y1, x2, y2):
    return {"type": "Polygon", "coordinates": [[(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]]}


def _trained():
    data = np.zeros((20, 20), dtype=np.float32)
    data[:, 10:] = 1
    features = _features(data)
    labels = data.astype(np.int8)
    sample = PVTrainingSample(features, labels, "training", "known synthetic truth")
    return PVFootprintModel.fit([sample], n_estimators=8, min_samples_leaf=1), features, labels


def test_features_calibrate_align_and_preserve_native_sources():
    images = _images()
    original = images["swir16"].data.copy()
    features = build_pv_features(images)
    assert features.feature_names == PV_FEATURE_NAMES
    assert features.data.shape == (10, 10, 9)
    assert features.valid_mask.all()
    assert features.pixel_area_m2 == 100
    np.testing.assert_allclose(
        features.data[3, 3, :6], [0.1, 0.11, 0.12, 0.13, 0.14, 0.15], atol=1e-7
    )
    np.testing.assert_allclose(
        features.data[3, 3, 6:], [0.01 / 0.25, 0.01 / 0.27, -0.03 / 0.25], atol=1e-7
    )
    assert features.provenance["sources"]["swir16"]["resampling"] == "bilinear"
    assert features.provenance["sources"]["scl"]["resampling"] == "nearest"
    assert features.provenance["sources"]["red"]["resampling"] == "none"
    np.testing.assert_array_equal(images["swir16"].data, original)
    assert images["swir16"].data.shape == (1, 5, 5)


def test_features_use_scl_classes_and_explicit_water_override():
    images = _images()
    values = np.full((10, 10), 5)
    values.ravel()[:12] = np.arange(12)
    images["scl"] = _image("scl", values)
    features = build_pv_features(images)
    np.testing.assert_array_equal(
        features.valid_mask.ravel()[:12],
        [False, False, False, False, True, True, False, True, False, False, False, False],
    )
    water_allowed = build_pv_features(
        images, excluded_scl=tuple(code for code in DEFAULT_EXCLUDED_SCL if code != 6)
    )
    assert water_allowed.valid_mask.ravel()[6]
    with pytest.raises(ValueError, match="SCL codes"):
        build_pv_features(images, excluded_scl=(99,))


def test_feature_masks_invalid_sources_and_preserves_valid_negative_reflectance():
    images = _images()
    values = images["red"].data.copy()
    values[0, 0, 0] = 900  # Valid reflectance -0.01; not zero-clipped.
    values[0, 0, 1] = np.ma.masked
    images["red"] = replace(images["red"], data=values)
    features = build_pv_features(images)
    assert features.data[0, 0, 2] == pytest.approx(-0.01)
    assert features.valid_mask[0, 0]
    assert not features.valid_mask[0, 1]
    # Zero normalized-difference denominator must be unknown, not invented.
    images["nir"] = replace(images["nir"], data=np.ma.array(np.full((1, 10, 10), 1100)))
    assert not build_pv_features(images).valid_mask[0, 0]


@pytest.mark.parametrize(
    "change", ["missing", "scene", "area", "asset", "geographic", "rotation", "scl"]
)
def test_feature_input_guards(change):
    images = _images()
    if change == "missing":
        del images["nir"]
    elif change == "scene":
        images["nir"] = replace(images["nir"], scene_id="other")
    elif change == "area":
        images["nir"] = replace(images["nir"], bbox_wgs84=(0, 0, 1, 1))
    elif change == "asset":
        images["nir"] = replace(images["nir"], asset_key="red")
    elif change == "geographic":
        images["red"] = replace(images["red"], crs="EPSG:4326")
    elif change == "rotation":
        images["red"] = replace(images["red"], transform=(10, 1, 350000, 0, -10, 3120000))
    else:
        images["scl"] = _image("scl", np.full((5, 5), 5.5), resolution=20)
    with pytest.raises(ValueError):
        build_pv_features(images)


def test_feature_grid_memory_limit():
    with pytest.raises(ValueError, match="max_pixels"):
        build_pv_features(_images(), max_pixels=99)


def test_label_rasterization_unknown_default_buffer_and_explicit_background():
    features = _features(np.zeros((10, 10)))
    positive = [_polygon(350030, 3119930, 350070, 3119970)]
    labels = rasterize_pv_labels(features, positive, geometry_crs=features.crs)
    assert np.count_nonzero(labels == 1) == 16
    assert np.count_nonzero(labels == -1) == 84
    buffered = rasterize_pv_labels(
        features,
        positive,
        geometry_crs=features.crs,
        background_is_negative=True,
        boundary_buffer_m=10,
    )
    assert np.count_nonzero(buffered == 1) == 16
    assert np.count_nonzero(buffered == -1) == 20
    assert np.count_nonzero(buffered == 0) == 64
    valid = features.valid_mask.copy()
    valid[4, 4] = False
    masked = rasterize_pv_labels(
        replace(features, valid_mask=valid), positive, geometry_crs=features.crs
    )
    assert masked[4, 4] == -1


def test_explicit_negative_labels_and_overlap_rejection():
    features = _features(np.zeros((10, 10)))
    positive = [_polygon(350030, 3119930, 350070, 3119970)]
    negative = [_polygon(350000, 3119900, 350020, 3119920)]
    labels = rasterize_pv_labels(
        features, positive, negative_geometries=negative, geometry_crs=features.crs
    )
    assert np.count_nonzero(labels == 0) == 4
    with pytest.raises(ValueError, match="overlap"):
        rasterize_pv_labels(
            features, positive, negative_geometries=positive, geometry_crs=features.crs
        )


def test_labels_reject_invalid_geometry_and_project_wgs84():
    from rasterio.warp import transform_geom

    features = _features(np.zeros((10, 10)))
    native = _polygon(350030, 3119930, 350070, 3119970)
    geographic = transform_geom(features.crs, "EPSG:4326", native)
    labels = rasterize_pv_labels(features, [geographic])
    assert np.count_nonzero(labels == 1) == 16
    invalid = {"type": "Polygon", "coordinates": [[(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)]]}
    with pytest.raises(ValueError, match="valid"):
        rasterize_pv_labels(features, [invalid])
    with pytest.raises(ValueError, match="Polygon"):
        rasterize_pv_labels(features, [{"type": "Point", "coordinates": [0, 0]}])


def test_training_and_image_only_prediction_transfer_to_held_out_site():
    model, training, labels = _trained()
    held_out = _features(training.data, bbox=(1, 1, 1.01, 1.01), scene="unseen")
    result = model.predict(held_out, min_area_m2=100)
    np.testing.assert_array_equal(result.mask, labels)
    assert result.metadata["inference_uses_osm"] is False
    assert result.metadata["overlaps_training_area"] is False
    assert result.area_m2 == 20_000
    metrics = model.evaluate(
        held_out,
        labels,
        site_id="held-out",
        label_source="independent synthetic truth",
        min_area_m2=100,
    )
    assert metrics["spatially_disjoint_from_training"] is True
    assert metrics["area_filtered"]["iou"] == 1
    assert metrics["raw_threshold"]["f1"] == 1


def test_held_out_guard_blocks_same_id_or_area_under_different_scene():
    model, training, labels = _trained()
    with pytest.raises(ValueError, match="geographically disjoint"):
        model.evaluate(
            replace(training, scene_id="later-scene"),
            labels,
            site_id="different-name",
            label_source="test",
        )
    with pytest.raises(ValueError, match="geographically disjoint"):
        model.evaluate(
            _features(training.data, bbox=(2, 2, 3, 3)),
            labels,
            site_id="training",
            label_source="test",
        )
    assert model.predict(training).metadata["overlaps_training_area"] is True


@pytest.mark.parametrize("change", ["bbox", "bounds", "pixel_area"])
def test_stale_geospatial_metadata_cannot_bypass_holdout_guard(change):
    model, features, labels = _trained()
    if change == "bbox":
        features = replace(features, bbox_wgs84=(0, 0, 1, 1))
    elif change == "bounds":
        features = replace(features, bounds=(0, 0, 200, 200))
    else:
        features = replace(features, pixel_area_m2=1000)
    with pytest.raises(ValueError, match="actual grid"):
        model.evaluate(features, labels, site_id="new-name", label_source="same actual raster")


def test_ground_image_bounds_must_match_native_grid():
    images = _images()
    images["red"] = replace(images["red"], bounds=(0, 0, 100, 100))
    with pytest.raises(ValueError, match="bounds disagree"):
        build_pv_features(images)


def test_training_reproducibility_sampling_and_provenance():
    _, features, labels = _trained()
    sample = PVTrainingSample(features, labels, "training", "synthetic labels")
    a = PVFootprintModel.fit([sample], n_estimators=5, max_samples_per_class=20, random_state=42)
    b = PVFootprintModel.fit([sample], n_estimators=5, max_samples_per_class=20, random_state=42)
    assert a.model_id == b.model_id
    assert a.metadata["training"][0]["selected_pixels"] == {"0": 20, "1": 20}
    assert a.metadata["probabilities_calibrated"] is False


@pytest.mark.parametrize("change", ["one_class", "unknown", "bad_label", "no_source", "no_id"])
def test_training_requires_two_classes_and_label_provenance(change):
    features = _features(np.zeros((5, 5)))
    labels = np.zeros((5, 5), dtype=np.int8)
    labels[:, 3:] = 1
    site_id, source = "site", "independent source"
    if change == "one_class":
        labels[:] = 1
    elif change == "unknown":
        labels[:] = -1
    elif change == "bad_label":
        labels[0, 0] = 2
    elif change == "no_source":
        source = ""
    else:
        site_id = ""
    with pytest.raises(ValueError):
        PVFootprintModel.fit([PVTrainingSample(features, labels, site_id, source)], n_estimators=2)


def test_predictions_filter_components_retain_holes_and_preserve_invalid_mask():
    model, _, _ = _trained()
    values = np.zeros((10, 10), dtype=np.float32)
    values[1:6, 1:6] = 1
    values[3, 3] = 0  # A hole, not filled by component filtering.
    values[8, 8] = 1  # A 100-square-metre isolated pixel is filtered.
    features = _features(values, bbox=(2, 2, 2.1, 2.1))
    valid = features.valid_mask.copy()
    valid[0, 0] = False
    result = model.predict(replace(features, valid_mask=valid), min_area_m2=500)
    assert result.mask.mask[0, 0]
    assert not result.mask[3, 3]
    assert not result.mask[8, 8]
    assert result.probabilities[8, 8] == 1  # Scores precede area filtering.
    assert result.area_m2 == 2400
    assert len(result.geojson["features"]) == 1
    polygon = result.geojson["features"][0]
    assert len(polygon["geometry"]["coordinates"]) == 2
    assert polygon["properties"]["pixel_count"] == 24
    lon, lat = polygon["geometry"]["coordinates"][0][0]
    assert -17 < lon < -16 and 28 < lat < 29


def test_prediction_schema_and_parameter_validation():
    model, features, _ = _trained()
    with pytest.raises(ValueError, match="feature names"):
        model.predict(replace(features, feature_names=("other",)))
    for threshold in (0, 1, np.nan, True):
        with pytest.raises(ValueError, match="threshold"):
            model.predict(features, threshold=threshold)
    with pytest.raises(ValueError, match="min_area_m2"):
        model.predict(features, min_area_m2=-1)


def test_forest_json_round_trip_is_exact_and_non_executable(tmp_path):
    model, features, _ = _trained()
    destination = model.save(tmp_path / "model.json")
    loaded = PVFootprintModel.load(destination)
    assert loaded.model_id == model.model_id
    np.testing.assert_array_equal(
        loaded.predict(features).probabilities, model.predict(features).probabilities
    )
    assert json.loads(destination.read_text())["format"] == "orbitalpv-pv-forest-v1"
    with pytest.raises(FileExistsError):
        model.save(destination)


def test_numeric_tree_inference_matches_sklearn_fractional_leaf_scores(monkeypatch):
    from sklearn import ensemble

    captured = []
    original = ensemble.RandomForestClassifier

    class CapturedForest(original):
        def fit(self, x, y, **kwargs):
            result = super().fit(x, y, **kwargs)
            captured.append(self)
            return result

    monkeypatch.setattr(ensemble, "RandomForestClassifier", CapturedForest)
    rng = np.random.default_rng(42)
    features = _features(rng.uniform(size=(20, 20, 3)))
    labels = (features.data[:, :, 0] + features.data[:, :, 1] > 1).astype(np.int8)
    labels[::5, :] = 1 - labels[::5, :]
    model = PVFootprintModel.fit(
        [PVTrainingSample(features, labels, "training", "synthetic noisy truth")],
        n_estimators=7,
        min_samples_leaf=10,
    )
    held_out = _features(rng.uniform(size=(8, 8, 3)), bbox=(2, 2, 2.01, 2.01))
    actual = model.predict(held_out, min_area_m2=0).probabilities.data.ravel()
    expected = captured[0].predict_proba(held_out.data.reshape(-1, 3))[:, 1]
    assert np.any((expected > 0) & (expected < 1))
    np.testing.assert_allclose(actual, expected, atol=3e-8)


@pytest.mark.parametrize("change", ["cycle", "feature", "probability", "provenance", "format"])
def test_json_rejects_corrupt_models(tmp_path, change):
    model, _, _ = _trained()
    path = model.save(tmp_path / "model.json")
    payload = json.loads(path.read_text())
    if change == "cycle":
        payload["trees"][0]["left"][0] = 0
    elif change == "feature":
        payload["trees"][0]["feature"][0] = 999
    elif change == "probability":
        payload["trees"][0]["probability"][0] = 2
    elif change == "provenance":
        payload["metadata"]["training"] = []
    else:
        payload["format"] = "pickle"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        PVFootprintModel.load(path)


def test_metrics_counts_unknowns_masks_and_undefined_cases():
    truth = np.array([[1, 1, 0], [0, -1, 1]], dtype=np.int8)
    prediction = np.ma.array([[1, 0, 1], [0, 1, 0]], mask=[[0, 0, 0], [0, 0, 1]])
    result = evaluate_pv_mask(prediction, truth)
    assert {
        key: result[key]
        for key in ("true_positive", "false_positive", "false_negative", "true_negative")
    } == dict.fromkeys(("true_positive", "false_positive", "false_negative", "true_negative"), 1)
    assert result["iou"] == pytest.approx(1 / 3)
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["evaluated_pixels"] == 4
    assert result["labelled_coverage"] == 0.8
    empty = evaluate_pv_mask(np.zeros((2, 2), dtype=bool), np.full((2, 2), -1))
    assert empty["iou"] is None
    assert empty["precision"] is None
    assert empty["labelled_coverage"] is None
    no_positives = evaluate_pv_mask(np.zeros((2, 2), dtype=bool), np.zeros((2, 2), dtype=np.int8))
    assert no_positives["accuracy"] == 1
    assert no_positives["iou"] is None
    masked_labels = np.ma.array([[True, False]], mask=[[True, False]])
    masked = evaluate_pv_mask(np.array([[True, False]]), masked_labels)
    assert masked["labelled_pixels"] == 1
    assert masked["true_positive"] == 0


def test_raw_and_filtered_metrics_are_separate():
    model, _, _ = _trained()
    features = _features(np.eye(4), bbox=(3, 3, 3.01, 3.01))
    metrics = model.evaluate(
        features,
        np.eye(4, dtype=np.int8),
        site_id="different",
        label_source="synthetic truth",
        min_area_m2=500,
    )
    assert metrics["raw_threshold"]["iou"] == 1
    assert metrics["area_filtered"]["recall"] == 0
    assert metrics["area_filtered"]["precision"] is None
