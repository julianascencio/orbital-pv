"""Independent synthetic invariants for ground-research algorithms."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("scipy")
pytest.importorskip("shapely")
pytest.importorskip("sklearn")

from orbitalpv.ground_research import (
    SegmentationAdapter,
    adaptive_andpi,
    andpi_index,
    benchmark_segmentation,
    evaluate_geometry_capacity,
    fit_geometry_capacity_model,
    match_pv_changes,
    summarize_pv_geometry,
    supervised_segmentation_adapter,
)
from orbitalpv.pv_detection import PVFeatures, PVTrainingSample


def _sample(site="training", left=350_000):
    from rasterio.warp import transform_bounds

    labels = np.zeros((12, 12), dtype=np.int8)
    labels[:, 6:] = 1
    values = labels.astype(float)[..., None]
    bounds = (left, 3_119_880, left + 120, 3_120_000)
    features = PVFeatures(
        values,
        np.ones((12, 12), dtype=bool),
        ("synthetic_feature",),
        "EPSG:32628",
        (10, 0, left, 0, -10, 3_120_000),
        bounds,
        transform_bounds("EPSG:32628", "EPSG:4326", *bounds),
        "synthetic_scene",
        100.0,
        {"source": "synthetic independent unit-test fixture"},
    )
    return PVTrainingSample(features, labels, site, "synthetic exact labels")


def _bands(score):
    # B11=1 and every maximum-mixed band=1-score gives the requested index.
    score = np.asarray(score, dtype=float)
    return {
        name: np.ones(score.shape) if name == "swir16" else 1 - score
        for name in ("blue", "green", "red", "nir", "swir16", "swir22")
    }


def _collection(boxes):
    from shapely.geometry import box, mapping

    return {
        "type": "FeatureCollection",
        "metadata": {"source": "synthetic", "license": "CC0"},
        "features": [
            {
                "type": "Feature",
                "id": str(i),
                "geometry": mapping(box(*bounds)),
                "properties": {"source": "synthetic", "capacity_status": "unknown"},
            }
            for i, bounds in enumerate(boxes)
        ],
    }


def _capacity(prefix, sizes, *, multiplier=1.0, country="A"):
    sizes = np.asarray(sizes, dtype=float)
    return pd.DataFrame(
        {
            "site_id": [f"{prefix}-{i}" for i in range(len(sizes))],
            "footprint_area_m2": sizes,
            "capacity_mw": sizes / 10_000 * multiplier,
            "country": country,
        }
    )


def test_andpi_matches_primary_spectral_formula_and_masks_unusable_denominator():
    bands = {
        name: np.full((2, 2), value)
        for name, value in {
            "blue": 0.12,
            "green": 0.15,
            "red": 0.2,
            "nir": 0.1,
            "swir16": 0.4,
            "swir22": 0.25,
        }.items()
    }
    bands["swir16"][0, 0] = 0
    result = andpi_index(bands)
    assert np.ma.getmaskarray(result)[0, 0]
    assert result[1, 1] == pytest.approx((0.4 - 0.25) / (0.4 + 1e-10))
    # Adding NIR to the maximum can reverse the index; it is not normalized difference SWIR/NIR.
    bands["nir"][1, 1] = 0.6
    assert andpi_index(bands)[1, 1] < 0
    with pytest.raises(ValueError, match="identical"):
        andpi_index({**bands, "blue": np.zeros((3, 3))})


def test_adaptive_andpi_valley_fallback_and_prior_are_explicit():
    scores = np.r_[np.full(400, 0.08), np.full(400, 0.32)].reshape(20, 40)
    result = adaptive_andpi(_bands(scores), mode="new")
    assert result.metadata["decision"] == "histogram_valley"
    assert 0.08 < result.metadata["threshold"] < 0.32
    assert int(result.mask.sum()) == 400
    assert result.metadata["uses_prior_candidates"] is False
    no_peaks = adaptive_andpi(_bands(np.zeros((8, 8))), mode="new")
    assert no_peaks.metadata["threshold"] == 1
    assert not no_peaks.mask.any()
    retained = adaptive_andpi(
        _bands(np.pad(np.full((4, 4), 0.2), ((0, 4), (0, 4)))),
        candidate_mask=np.ones((8, 8), dtype=bool),
        mode="old",
        retain_ratio=0.8,
    )
    assert retained.mask.all()
    assert retained.metadata["uses_prior_candidates"] is True
    assert "prior_candidate_retention" in retained.metadata["decision"]
    equality = adaptive_andpi(_bands(np.zeros((8, 8))), mode="old")
    assert equality.metadata["threshold"] == 0
    assert equality.mask.all()  # Source uses >=, not >, at the threshold.


@pytest.mark.parametrize("method", ["logistic", "random_forest"])
def test_supervised_alternatives_generalize_on_disjoint_exact_fixture(method):
    training, heldout = _sample(), _sample("heldout", 370_000)
    adapter = supervised_segmentation_adapter([training], method=method, random_state=3)
    result = benchmark_segmentation([adapter], [heldout])["results"][0]
    assert result["f1"] == 1
    assert result["iou"] == 1
    assert result["relative_area_bias"] == 0
    assert result["prediction_provenance"]["inference_receives_labels"] is False
    with pytest.raises(ValueError, match="Geographic leakage"):
        benchmark_segmentation([adapter], [replace(training, site_id="renamed_same_geography")])


def test_benchmark_uses_known_support_and_counts_false_positive_objects():
    sample = _sample("evaluation", 380_000)
    labels = np.zeros((12, 12), dtype=np.int8)
    labels[2:4, 2:4] = 1
    labels[8:, 8:] = -1
    output = labels == 1
    output[5, 5] = True  # fully labelled false positive
    output[8:10, 8:10] = True  # unknown object excluded from false positives
    adapter = SegmentationAdapter("known-mask", lambda _: output.astype(float))
    result = benchmark_segmentation([adapter], [replace(sample, labels=labels)])["results"][0]
    assert result["true_positive"] == 4
    assert result["false_positive"] == 1
    assert result["precision"] == 0.8
    assert result["area_bias_m2"] == 100
    assert result["false_positive_objects"] == 1
    assert result["objects_with_unknown_labels"] == 1
    assert result["evaluated_pixels"] == 128


def test_external_model_adapter_records_checkpoint_without_executing_it(tmp_path):
    weights = tmp_path / "panel.weights"
    weights.write_bytes(b"fixture, not an executable checkpoint")
    adapter = SegmentationAdapter.from_callable(
        "PANEL local runtime",
        lambda f: np.zeros(f.valid_mask.shape),
        weights_path=weights,
        license_name="caller accepted model terms",
    )
    output = adapter.predict(_sample().features)
    assert len(output.metadata["weights_sha256"]) == 64
    assert "architecture not implemented" in output.metadata["implementation"]
    invalid = SegmentationAdapter("bad-shape", lambda _: np.ones((2, 2)))
    with pytest.raises(ValueError, match="match"):
        invalid.predict(_sample().features)


def test_geometry_axis_is_not_tilt_or_facing_direction():
    result = summarize_pv_geometry(_collection([(-16.4, 28.0, -16.398, 28.0001)]))
    assert result.footprint_area_m2.iloc[0] > 0
    assert 80 < result.axis_azimuth_deg.iloc[0] < 100
    assert result.panel_tilt_deg.iloc[0] is None
    assert bool(result.axis_is_direction_ambiguous.iloc[0])
    assert result.source_properties.iloc[0]["capacity_status"] == "unknown"


def test_capacity_conformal_quantile_conversion_and_disjoint_groups():
    train = _capacity("train", np.linspace(100, 10_000, 30))
    # Nine residuals at log(2); 90% conformal rank=ceil(10*.9)=9.
    cal = _capacity("cal", np.linspace(100, 10_000, 9), multiplier=2, country="B")
    model = fit_geometry_capacity_model(
        train,
        cal,
        capacity_basis="DC",
        area_basis="module_footprint",
        source="synthetic unit-test fixture",
        group_column="country",
        ridge=0,
    )
    assert model.residual_quantile == pytest.approx(np.log(2))
    assert model.provenance["calibration_order_statistic"] == 9
    final = _capacity("test", [500, 1_000, 2_000], country="C")
    prediction = model.predict(final, area_basis="module_footprint")
    np.testing.assert_allclose(prediction.capacity_mw, [0.05, 0.1, 0.2])
    np.testing.assert_allclose(prediction.lower_mw, prediction.capacity_mw / 2)
    ac = model.predict(final, area_basis="module_footprint", output_basis="AC", dc_ac_ratio=1.2)
    np.testing.assert_allclose(ac.capacity_mw, prediction.capacity_mw / 1.2)
    assert evaluate_geometry_capacity(model, final)["coverage_observed"] == 1
    with pytest.raises(ValueError, match="disjoint"):
        evaluate_geometry_capacity(model, cal)
    with pytest.raises(ValueError, match="groups overlap"):
        evaluate_geometry_capacity(model, final.assign(country="A"))
    with pytest.raises(ValueError, match="missing or blank"):
        evaluate_geometry_capacity(model, final.assign(country=np.nan))
    with pytest.raises(ValueError, match="missing or blank"):
        evaluate_geometry_capacity(model, final.assign(country=" "))
    with pytest.raises(ValueError, match="cannot be predictive"):
        fit_geometry_capacity_model(
            train,
            cal,
            feature_names=("capacity_mw",),
            capacity_basis="DC",
            area_basis="x",
            source="x",
        )
    with pytest.raises(ValueError, match="finite interval"):
        fit_geometry_capacity_model(
            train, cal.iloc[:3], capacity_basis="DC", area_basis="x", source="x"
        )


def test_capacity_refuses_basis_and_extrapolation_ambiguity():
    model = fit_geometry_capacity_model(
        _capacity("a", np.arange(1, 20) * 100),
        _capacity("b", np.arange(1, 11) * 100),
        capacity_basis="reported",
        area_basis="OSM polygon",
        source="synthetic",
    )
    new = _capacity("c", [5_000])
    with pytest.raises(ValueError, match="extrapolates"):
        model.predict(new, area_basis="OSM polygon")
    with pytest.raises(ValueError, match="cannot be relabelled"):
        model.predict(
            new,
            area_basis="OSM polygon",
            allow_extrapolation=True,
            output_basis="DC",
            dc_ac_ratio=1.2,
        )
    with pytest.raises(ValueError, match="semantics"):
        model.predict(new, area_basis="module area", allow_extrapolation=True)


def test_two_date_split_merge_matching_and_observation_brackets():
    before = _collection([(0, 0, 0.02, 0.01), (1, 1, 1.01, 1.01)])
    after = _collection([(0, 0, 0.01, 0.01), (0.01, 0, 0.02, 0.01), (2, 2, 2.01, 2.01)])
    results = match_pv_changes(before, after, before_time="2024-01-01", after_time="2025-01-01")
    statuses = {row["status"] for row in results["changes"]}
    assert statuses == {"persistent_footprint", "not_redetected", "newly_observed"}
    persistent = next(row for row in results["changes"] if row["status"] == "persistent_footprint")
    assert persistent["split_or_merge"]
    assert persistent["group_iou"] == pytest.approx(1)
    assert all(row["change_window_start_exclusive"] is None for row in results["changes"])
    full = match_pv_changes(
        before, after, before_time="2024-01-01", after_time="2025-01-01", complete_coverage=True
    )
    added = next(row for row in full["changes"] if row["status"] == "added_between_observations")
    assert added["change_window_start_exclusive"].startswith("2024-01-01")
    assert "not electrical commissioning" in full["date_semantics"]
    with pytest.raises(ValueError, match="chronological"):
        match_pv_changes(before, after, before_time="2025-01-01", after_time="2024-01-01")
