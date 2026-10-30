"""Independent geometry, source provenance, and calibration-domain checks."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("shapely")
pyproj = pytest.importorskip("pyproj")
pytest.importorskip("sklearn")
from shapely.geometry import shape  # noqa: E402

from orbitalpv.pv_inventory import (  # noqa: E402
    cluster_pv_farms,
    evaluate_pv_capacity,
    fit_pv_capacity_model,
    osm_pv_features,
)

TAGS = {"power": "generator", "generator:source": "solar", "generator:method": "photovoltaic"}
ROOT = Path(__file__).resolve().parents[1]


def _way(identifier, coordinates, **tags):
    return {
        "type": "way",
        "id": identifier,
        "geometry": [{"lon": x, "lat": y} for x, y in coordinates],
        "tags": {**TAGS, **tags},
    }


def _square(identifier=1, x=0.0, y=0.0, width=0.001, **tags):
    return _way(
        identifier, [(x, y), (x + width, y), (x + width, y + width), (x, y + width), (x, y)], **tags
    )


def _node(identifier, x, y=0.0):
    return {"type": "node", "id": identifier, "lon": x, "lat": y, "tags": TAGS.copy()}


def _raw(*elements):
    return {"elements": list(elements), "osm3s": {"timestamp_osm_base": "2026-10-30T00:00:00Z"}}


def _first(collection):
    return collection["features"][0]["properties"]


def test_osm_conversion_retains_semantics_provenance_and_input():
    raw = _raw(_square(), _node(2, 0.01))
    original = deepcopy(raw)
    result = osm_pv_features(raw)
    assert raw == original
    assert len(result["features"]) == 2
    feature = next(f for f in result["features"] if f["id"] == "way/1")
    assert feature["properties"]["element_kind"] == "generator"
    assert feature["properties"]["tags"] == TAGS
    assert feature["properties"]["source_ids"] == ["way/1"]
    assert result["metadata"]["osm_timestamp"] == "2026-10-30T00:00:00Z"
    json.dumps(result, allow_nan=False)


def test_unconfirmed_and_thermal_solar_are_not_automatically_pv():
    unknown = _square(1)
    unknown["tags"].pop("generator:method")
    thermal = _square(2, **{"generator:method": "thermal"})
    result = osm_pv_features(_raw(unknown, thermal))
    assert result["features"] == []
    assert len(result["metadata"]["excluded"]) == 2
    permitted = osm_pv_features(_raw(unknown, thermal), require_photovoltaic=False)
    assert len(permitted["features"]) == 1
    assert _first(permitted)["photovoltaic_confirmed"] is False


def test_polygon_missing_vertices_open_rings_and_self_intersection_raise():
    malformed = [
        _way(1, [(0, 0), (1, 0), (0, 1)]),
        _way(2, [(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)]),
        {"type": "way", "id": 3, "tags": TAGS, "geometry": [{"lon": 0, "lat": 0}, None]},
    ]
    for element in malformed:
        with pytest.raises(ValueError):
            osm_pv_features(_raw(element))
    skipped = osm_pv_features(_raw(*malformed), on_invalid="skip")
    assert skipped["features"] == []
    assert len(skipped["metadata"]["excluded"]) == 3


def test_conflicting_ids_incomplete_response_and_antimeridian_rejected():
    with pytest.raises(ValueError, match="Conflicting"):
        osm_pv_features(_raw(_square(1), _square(1, x=1)))
    with pytest.raises(ValueError, match="incomplete"):
        osm_pv_features({**_raw(), "remark": "runtime error"})
    with pytest.raises(ValueError, match="antimeridian"):
        osm_pv_features(_raw(_way(1, [(179, 0), (-179, 0), (-179, 1), (179, 1), (179, 0)])))


def test_multipolygon_joins_fragmented_rings_and_preserves_inner_hole():
    exterior = [(0, 0), (3, 0), (3, 3), (0, 3), (0, 0)]
    hole = [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]
    members = []
    for reference, coordinates, role in [
        (11, exterior[:3], "outer"),
        (12, exterior[2:], "outer"),
        (13, hole, "inner"),
    ]:
        members.append(
            {
                "type": "way",
                "ref": reference,
                "role": role,
                "geometry": [{"lon": x, "lat": y} for x, y in coordinates],
            }
        )
    relation: dict[str, Any] = {
        "type": "relation",
        "id": 1,
        "tags": {**TAGS, "type": "multipolygon"},
        "members": members,
    }
    result = osm_pv_features(_raw(relation))
    geometry = shape(result["features"][0]["geometry"])
    assert geometry.area == pytest.approx(8)
    assert len(geometry.interiors) == 1
    broken = deepcopy(relation)
    broken["members"].pop(1)
    with pytest.raises(ValueError, match="closed"):
        osm_pv_features(_raw(broken))


def test_multipolygon_hole_outside_outer_and_nested_relations_rejected():
    outer = _square()["geometry"]
    inner = _square(x=1)["geometry"]
    relation: dict[str, Any] = {
        "type": "relation",
        "id": 1,
        "tags": {**TAGS, "type": "multipolygon"},
        "members": [
            {"type": "way", "ref": 2, "role": "outer", "geometry": outer},
            {"type": "way", "ref": 3, "role": "inner", "geometry": inner},
        ],
    }
    with pytest.raises(ValueError, match="not contained"):
        osm_pv_features(_raw(relation))
    relation["members"] = [{"type": "relation", "ref": 2, "role": "outer"}]
    with pytest.raises(ValueError, match="nested"):
        osm_pv_features(_raw(relation))


def test_relation_can_resolve_way_and_node_references():
    nodes = [
        {"type": "node", "id": i, "lon": x, "lat": y}
        for i, (x, y) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)], start=1)
    ]
    member = {"type": "way", "id": 10, "nodes": [1, 2, 3, 4, 1]}
    relation: dict[str, Any] = {
        "type": "relation",
        "id": 20,
        "tags": {**TAGS, "type": "multipolygon"},
        "members": [{"type": "way", "ref": 10, "role": "outer"}],
    }
    result = osm_pv_features(_raw(*nodes, member, relation))
    assert len(result["features"]) == 1
    assert shape(result["features"][0]["geometry"]).area == 1


def test_semantic_area_separates_parent_land_from_panels_and_unions_overlap():
    parent = _square(
        1,
        width=0.004,
        **{"power": "plant", "plant:source": "solar", "plant:method": "photovoltaic"},
    )
    rows = [_square(2, x=0.001, y=0.001, width=0.001), _square(3, x=0.0015, y=0.001, width=0.001)]
    duplicate = deepcopy(rows[0])
    duplicate["id"] = 4
    features = osm_pv_features(_raw(parent, *rows, duplicate, _node(5, 0.0012, 0.0012)))
    result = cluster_pv_farms(features)
    assert len(result["features"]) == 1
    props = _first(result)
    # 1.5 nonoverlapping row-square units, inside a 16-unit site boundary.
    assert props["panel_area_m2"] / props["plant_area_m2"] == pytest.approx(1.5 / 16, rel=2e-5)
    assert props["osm_polygon_area_m2"] == pytest.approx(props["plant_area_m2"])
    assert props["source_feature_count"] == 5
    assert props["unique_geometry_role_count"] == 4
    assert props["capacity_area_basis"] == "generator_panel_area"
    assert props["capacity_area_m2"] == props["panel_area_m2"]
    assert props["landscape_area_m2"] >= props["plant_area_m2"] - 1e-6


def test_whole_plant_only_does_not_fabricate_panel_area():
    result = cluster_pv_farms(osm_pv_features(_raw(_square(**{"power": "plant"}))))
    props = _first(result)
    assert props["panel_area_m2"] is None
    assert props["capacity_area_m2"] is None
    assert props["plant_area_m2"] > 0
    assert props["is_cluster"] is False


def test_duplicate_point_does_not_manufacture_cluster():
    result = cluster_pv_farms(osm_pv_features(_raw(_node(1, 0), _node(2, 0))))
    assert len(result["features"]) == 1
    assert _first(result)["source_feature_count"] == 2
    assert _first(result)["unique_geometry_role_count"] == 1
    assert _first(result)["is_cluster"] is False
    dropped = cluster_pv_farms(
        osm_pv_features(_raw(_node(1, 0), _node(2, 0))), keep_singletons=False
    )
    assert dropped["features"] == []


def test_point_distances_and_singletons_are_computed_in_metres():
    forward = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    nodes = [_node(i, *forward.transform(x, 0)) for i, x in enumerate([0, 300, 600, 2000], start=1)]
    result = cluster_pv_farms(osm_pv_features(_raw(*nodes)))
    assert sorted(p["properties"]["source_feature_count"] for p in result["features"]) == [1, 3]
    assert sum(p["properties"]["is_cluster"] for p in result["features"]) == 1
    assert all(p["properties"]["panel_area_m2"] is None for p in result["features"])


def test_historical_profile_uses_polygon_800m_point_400m_and_proxy_units():
    inverse = pyproj.Transformer.from_crs("ESRI:54012", "EPSG:4326", always_xy=True)
    polygons = []
    for identifier, x in enumerate([0, 700], start=1):
        coords = [
            inverse.transform(px, py)
            for px, py in [(x, 0), (x + 100, 0), (x + 100, 100), (x, 100), (x, 0)]
        ]
        polygons.append(_way(identifier, coords, power="plant"))
    nodes = [_node(i, *inverse.transform(x, 2000)) for i, x in enumerate([0, 350, 1100], start=10)]
    result = cluster_pv_farms(osm_pv_features(_raw(*polygons, *nodes)), profile="dunnett2020")
    assert result["metadata"]["polygon_eps_m"] == 800
    assert len(result["features"]) == 3
    polygroup = next(
        f["properties"] for f in result["features"] if f["properties"]["plant_feature_count"]
    )
    assert polygroup["osm_polygon_area_m2"] == pytest.approx(20_000, rel=1e-8)
    assert polygroup["capacity_area_m2"] == pytest.approx(20_000, rel=1e-8)
    assert polygroup["panel_area_m2"] is None
    assert polygroup["capacity_area_basis"] == "osm_polygon_proxy"
    pointgroups = [
        f["properties"] for f in result["features"] if not f["properties"]["plant_feature_count"]
    ]
    assert sorted(p["capacity_area_m2"] for p in pointgroups) == pytest.approx(
        [10_000, 20_000], rel=1e-8
    )
    assert all(p["capacity_area_basis"] == "median_polygon_imputation" for p in pointgroups)


def test_historical_nested_rows_and_inside_points_do_not_double_area():
    parent = _square(1, width=0.004, power="plant")
    row = _square(2, x=0.001, y=0.001)
    result = cluster_pv_farms(
        osm_pv_features(_raw(parent, row, _node(3, 0.002, 0.002))), profile="dunnett2020"
    )
    assert len(result["features"]) == 1
    props = _first(result)
    assert props["source_feature_count"] == 3
    assert props["is_cluster"] is False
    assert props["panel_area_m2"] / props["osm_polygon_area_m2"] == pytest.approx(1 / 16, rel=2e-5)
    assert props["capacity_area_m2"] == props["osm_polygon_area_m2"]


def test_historical_single_polygon_preserves_concavity_and_holes():
    outer = [(0, 0), (0.004, 0), (0.004, 0.004), (0.002, 0.004), (0.002, 0.002), (0, 0.002), (0, 0)]
    hole = [
        (0.0005, 0.0005),
        (0.0015, 0.0005),
        (0.0015, 0.0015),
        (0.0005, 0.0015),
        (0.0005, 0.0005),
    ]
    relation = {
        "type": "relation",
        "id": 1,
        "tags": {**TAGS, "type": "multipolygon", "power": "plant"},
        "members": [
            {
                "type": "way",
                "ref": index,
                "role": role,
                "geometry": [{"lon": x, "lat": y} for x, y in coordinates],
            }
            for index, (coordinates, role) in enumerate(
                [(outer, "outer"), (hole, "inner")], start=2
            )
        ],
    }
    features = osm_pv_features(_raw(relation))
    historical = cluster_pv_farms(features, profile="dunnett2020")
    props = _first(historical)
    assert props["landscape_area_m2"] == pytest.approx(props["osm_polygon_area_m2"])
    restored = shape(historical["features"][0]["geometry"])
    original = shape(features["features"][0]["geometry"])
    assert len(restored.interiors) == 1
    assert restored.area == pytest.approx(original.area, rel=1e-8)
    assert restored.area < restored.convex_hull.area


def test_semantic_profile_rejects_broad_extent_with_tiling_guidance():
    features = osm_pv_features(_raw(_node(1, 0), _node(2, 6)))
    with pytest.raises(ValueError, match="tile broader inventories"):
        cluster_pv_farms(features)
    # The historical profile explicitly retains the paper's global projection.
    assert len(cluster_pv_farms(features, profile="dunnett2020")["features"]) == 2


def test_empty_and_invalid_clustering_requests():
    empty = osm_pv_features(_raw())
    assert cluster_pv_farms(empty)["features"] == []
    bad_kwargs: tuple[dict[str, Any], ...] = (
        {"eps_m": -1},
        {"min_samples": True},
        {"min_samples": 1},
        {"profile": "other"},
        {"polygon_eps_m": 700},
    )
    for kwargs in bad_kwargs:
        with pytest.raises(ValueError):
            cluster_pv_farms(empty, **kwargs)


@pytest.mark.parametrize(
    "name,plants,generators", [("cestas", 1, 22), ("rengo", 1, 0), ("tenerife", 2, 50)]
)
def test_bundled_real_sites_preserve_source_area_semantics(name, plants, generators):
    raw = json.loads(
        (ROOT / "examples" / "ground_imagery" / "_data" / f"{name}-osm.json").read_text()
    )
    features = osm_pv_features(raw)
    assert len(features["features"]) == plants + generators
    result = cluster_pv_farms(features)
    assert sum(f["properties"]["plant_feature_count"] for f in result["features"]) == plants
    assert sum(f["properties"]["generator_feature_count"] for f in result["features"]) == generators
    assert (sum(f["properties"]["panel_area_m2"] or 0 for f in result["features"]) > 0) == (
        generators > 0
    )
    json.dumps(result, allow_nan=False)


def _calibration(noise=False):
    areas = np.geomspace(20_000, 2_000_000, 30)
    capacity = 20 * (areas / 1_000_000) ** 0.8
    if noise:
        capacity *= 1 + np.random.default_rng(7).normal(0, 0.05, areas.size)
    model = fit_pv_capacity_model(
        areas,
        capacity,
        urban=[False] * areas.size,
        capacity_basis="DC",
        area_basis="generator_panel_area",
        source="Synthetic independent calibration fixture; not observed plants",
    )
    return model, areas, capacity


def test_capacity_fit_recovers_known_relation_and_holds_units():
    model, areas, actual = _calibration()
    assert model.boxcox_lambda == 0
    predicted = model.predict(areas, urban=[False] * len(areas), area_basis="generator_panel_area")
    np.testing.assert_allclose(predicted.mean_mw, actual, rtol=1e-8)
    assert model.n_training == 30 and model.n_excluded == 0
    assert model.training_area_range_m2 == (20_000, 2_000_000)
    assert model.capacity_basis == "DC"
    assert model.fit_rmse_mw < 1e-8
    metrics = evaluate_pv_capacity(actual, predicted)
    assert metrics["r2"] == pytest.approx(1)
    assert metrics["n_evaluated"] == 30


def test_capacity_domain_guards_preserve_unknown_and_extrapolation_status():
    model, _, _ = _calibration()
    values = [100_000, 100_000, 100_000, 10_000, 3_000_000]
    pred = model.predict(
        values, urban=[False, True, None, False, False], area_basis="generator_panel_area"
    )
    assert pred.eligible.tolist() == [True, False, False, False, False]
    assert pred.extrapolated.tolist() == [False, False, False, True, True]
    assert np.isnan(pred.mean_mw[1:]).all()
    assert pred.reasons == (
        "within_calibration_range",
        "urban_or_unknown",
        "urban_or_unknown",
        "area_below_domain",
        "extrapolation_withheld",
    )
    allowed = model.predict(
        [3_000_000], urban=[False], area_basis="generator_panel_area", allow_extrapolation=True
    )
    assert allowed.eligible[0] and allowed.extrapolated[0]
    assert np.isfinite(allowed.mean_mw[0])
    with pytest.raises(ValueError, match="area_basis"):
        model.predict([100_000], urban=[False], area_basis="osm_polygon_proxy")
    with pytest.raises(ValueError, match="booleans"):
        model.predict([100_000], urban=[0], area_basis="generator_panel_area")


def test_capacity_intervals_and_heldout_metrics_report_exclusions():
    model, _, _ = _calibration(noise=True)
    areas = np.array([70_000, 180_000, 800_000, 5_000_000])
    actual = 20 * (areas / 1_000_000) ** 0.8
    pred = model.predict(areas, urban=[False] * 4, area_basis="generator_panel_area")
    assert np.all(pred.lower_mw[:3] <= pred.mean_mw[:3])
    assert np.all(pred.upper_mw[:3] >= pred.mean_mw[:3])
    metrics = evaluate_pv_capacity(actual, pred)
    assert metrics["n_total"] == 4 and metrics["n_evaluated"] == 3 and metrics["n_withheld"] == 1
    assert metrics["n_extrapolated"] == 1
    assert metrics["rmse_mw"] == pytest.approx(
        np.sqrt(np.mean((pred.mean_mw[:3] - actual[:3]) ** 2))
    )
    assert 0 <= metrics["interval_coverage"] <= 1
    assert metrics["r2"] > 0.95


def test_calibration_exclusions_are_counted_and_unknown_is_not_rural():
    _, areas, capacities = _calibration()
    model = fit_pv_capacity_model(
        np.r_[areas, 100, 100_000, 100_000, 100_000],
        np.r_[capacities, 1, 1, 1, 1000],
        urban=[False] * 31 + [True, None, False],
        capacity_basis="reported",
        area_basis="osm_polygon_proxy",
        source="Fixture",
    )
    assert model.n_training == 30
    assert model.n_excluded == 4


def test_invalid_and_unidentifiable_capacity_calibrations_rejected():
    base: dict[str, Any] = dict(
        urban=[False] * 6, capacity_basis="AC", area_basis="osm_polygon_proxy", source="Test"
    )
    for areas, capacities in [
        ([20_000] * 6, [2] * 6),
        ([20_000, 30_000, 40_000, 50_000, 60_000, 70_000], [6, 5, 4, 3, 2, 1]),
        ([np.nan] * 6, [2] * 6),
        ([20_000] * 6, [0] * 6),
    ]:
        with pytest.raises(ValueError):
            fit_pv_capacity_model(areas, capacities, **base)
    short: dict[str, Any] = {**base, "urban": [False] * 3}
    with pytest.raises(ValueError, match="six"):
        fit_pv_capacity_model([20_000, 30_000, 40_000], [1, 2, 3], **short)


def test_no_eligible_predictions_report_null_metrics():
    model, _, _ = _calibration()
    pred = model.predict([100_000], urban=[None], area_basis="generator_panel_area")
    metrics = evaluate_pv_capacity([5], pred)
    assert metrics["n_evaluated"] == 0
    assert metrics["rmse_mw"] is None and metrics["r2"] is None
    json.dumps(metrics, allow_nan=False)
