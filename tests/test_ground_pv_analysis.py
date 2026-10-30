from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest
import rasterio

import orbitalpv as opv

DATA = Path(__file__).resolve().parents[1] / "examples/ground_imagery/_data"


@pytest.fixture(scope="module")
def sites():
    settings = json.loads((DATA / "pv-sites.json").read_text())
    return {
        key: opv.load_pv_site(
            **values,
            cache_dir=DATA,
            offline=True,
            assets=("visual", "scl", *opv.PV_SPECTRAL_BANDS),
        )
        for key, values in settings.items()
    }


@pytest.fixture(scope="module")
def prediction(sites):
    training = opv.prepare_pv_training_sample(sites["cestas"], background_is_negative=True)
    model = opv.PVFootprintModel.fit([training], n_estimators=5, random_state=0)
    features = opv.build_pv_features(sites["tenerife"].images)
    valid = features.valid_mask.copy()
    valid[0, 0] = False
    return model.predict(replace(features, valid_mask=valid))


def test_prepared_labels_do_not_assume_negative_background(sites):
    sample = opv.prepare_pv_training_sample(sites["cestas"])
    assert set(np.unique(sample.labels)) == {-1, 1}
    assert "background_is_negative=False" in sample.label_source
    assert "not independently surveyed" in sample.label_source


def test_prepared_labels_reject_whole_plant_as_panel_truth(sites):
    with pytest.raises(ValueError, match="plant boundary"):
        opv.prepare_pv_training_sample(sites["rengo"], background_is_negative=True)


def test_prepared_labels_preserve_explicit_site_id_and_map_date(sites):
    sample = opv.prepare_pv_training_sample(
        sites["tenerife"], site_id="independent-icor", background_is_negative=True
    )
    assert sample.site_id == "independent-icor"
    assert "2026-10-30" in sample.label_source
    assert set(np.unique(sample.labels)) == {-1, 0, 1}


def test_settlement_annotation_is_independent_and_preserves_unknown(sites):
    farms = opv.cluster_pv_farms(opv.osm_pv_features(sites["tenerife"].osm))
    settlement = opv.load_settlement_raster(DATA / "tenerife-ghsl.tif")
    result = opv.classify_pv_farms(farms, settlement)
    assert result["features"][0]["properties"]["urban"] is False
    assert "urban" not in farms["features"][0]["properties"]
    result["metadata"]["settlement_context"]["source"]["test_mutation"] = True
    assert "test_mutation" not in settlement.provenance
    farms["features"][0]["properties"].update(centroid_lon=0, centroid_lat=0)
    result = opv.classify_pv_farms(farms, settlement)
    assert result["features"][0]["properties"]["urban"] is None
    assert result["features"][0]["properties"]["water"] is None


def test_capacity_annotation_withholds_unknown_and_mismatched_predictors():
    areas = np.arange(2, 12, dtype=float) * 10000
    model = opv.fit_pv_capacity_model(
        areas,
        areas * 0.0001,
        urban=[False] * len(areas),
        capacity_basis="DC",
        area_basis="osm_polygon_proxy",
        source="Known independent test relation",
    )
    entries = [
        (40000, "osm_polygon_proxy", False),
        (40000, "osm_polygon_proxy", None),
        (40000, "generator_panel_area", False),
        (None, "osm_polygon_proxy", False),
        (400000, "osm_polygon_proxy", False),
    ]
    farms: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "capacity_area_m2": area,
                    "capacity_area_basis": basis,
                    "urban": urban,
                },
            }
            for area, basis, urban in entries
        ],
    }
    result = opv.estimate_pv_farm_capacity(farms, model)
    properties = [feature["properties"] for feature in result["features"]]
    assert properties[0]["estimated_capacity_mw"] == pytest.approx(4, rel=0.05)
    assert all(p["estimated_capacity_mw"] is None for p in properties[1:])
    assert [p["capacity_estimate_status"] for p in properties[1:]] == [
        "urban_or_unknown",
        "area_definition_mismatch",
        "missing_area",
        "extrapolation_withheld",
    ]
    assert "estimated_capacity_mw" not in json.dumps(farms)


def test_prediction_export_retains_grid_mask_provenance_and_no_overwrite(prediction, tmp_path):
    paths = opv.save_pv_prediction(prediction, tmp_path)
    with rasterio.open(paths["raster"]) as raster:
        assert raster.crs.to_string() == prediction.metadata["crs"]
        assert tuple(raster.transform)[:6] == tuple(prediction.metadata["transform"])
        values = raster.read(masked=True)
        assert values.mask[:, 0, 0].all()
        np.testing.assert_allclose(
            values[0].compressed(), prediction.probabilities.compressed(), rtol=1e-6
        )
        np.testing.assert_array_equal(values[1].compressed(), prediction.mask.compressed())
        assert raster.tags()["inference_uses_osm"] == "false"
    assert json.loads(paths["geojson"].read_text()) == json.loads(json.dumps(prediction.geojson))
    before = paths["raster"].read_bytes()
    with pytest.raises(FileExistsError):
        opv.save_pv_prediction(prediction, tmp_path)
    assert paths["raster"].read_bytes() == before


def test_plot_does_not_turn_masked_reference_into_positive(sites, prediction):
    reference = np.ma.array(np.ones(prediction.mask.shape), mask=True)
    figure, axes = opv.plot_pv_detection(sites["tenerife"], prediction, reference_labels=reference)
    assert [text.get_text() for text in axes[2].get_legend().get_texts()] == ["Image prediction"]
    assert len(axes[2].collections) == 0
    plt.close(figure)


def test_plot_rejects_stale_prediction_grid(sites, prediction):
    metadata = dict(prediction.metadata)
    metadata["transform"] = [10, 0, 0, 0, -10, 0]
    with pytest.raises(ValueError, match="native grid"):
        opv.plot_pv_detection(sites["tenerife"], replace(prediction, metadata=metadata))
