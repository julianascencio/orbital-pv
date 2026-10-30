"""Site loading tests use mocked providers and tiny local source rasters."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest

from space_pv_connectors import ground_site
from space_pv_connectors.ground_imagery import Sentinel2GroundConnector
from space_pv_connectors.ground_osm import OpenStreetMapEnergyConnector
from space_pv_connectors.ground_site import load_pv_site

rio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402

BBOX = (-0.98, 0.94, -0.94, 0.97)
SEARCH: dict[str, Any] = {"bbox": BBOX, "time_min": "2026-01-01", "time_max": "2026-03-01"}
DATA = Path(__file__).resolve().parents[1] / "examples" / "ground_imagery" / "_data"


def _item(identifier="scene-1"):
    return {
        "type": "Feature",
        "id": identifier,
        "collection": "sentinel-2-c1-l2a",
        "properties": {"datetime": "2026-02-11T14:00:00Z", "eo:cloud_cover": 0.1},
        "assets": {
            asset: {
                "href": f"https://example.test/{identifier}/{asset}.tif",
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data", "reflectance"] if asset == "red" else ["data"],
                "raster:bands": [
                    {"nodata": 0, "scale": 0.0001, "offset": -0.1}
                    if asset == "red"
                    else {"nodata": 0}
                    for _ in range(3 if asset == "visual" else 1)
                ],
            }
            for asset in ("visual", "red", "scl")
        },
    }


@pytest.fixture
def providers(tmp_path, monkeypatch):
    state = {"items": [_item(), _item("scene-2")], "requests": [], "raster_urls": []}

    def respond(request):
        state["requests"].append(request)
        if "earth-search" in request.url.host:
            return httpx.Response(
                200,
                json={"type": "FeatureCollection", "features": state["items"], "links": []},
            )
        return httpx.Response(
            200,
            json={
                "osm3s": {"timestamp_osm_base": "2026-10-30T10:00:00Z"},
                "elements": [
                    {
                        "type": "way",
                        "id": 123,
                        "tags": {"plant:source": "solar", "plant:method": "photovoltaic"},
                        "geometry": [{"lon": -0.97, "lat": 0.96}, {"lon": -0.95, "lat": 0.95}],
                    }
                ],
            },
        )

    def factory(cls):
        def create(**kwargs):
            connector = cls(**kwargs)
            connector._client.close()
            connector._client = httpx.Client(transport=httpx.MockTransport(respond))
            return connector

        return create

    monkeypatch.setattr(ground_site, "Sentinel2GroundConnector", factory(Sentinel2GroundConnector))
    monkeypatch.setattr(
        ground_site, "OpenStreetMapEnergyConnector", factory(OpenStreetMapEnergyConnector)
    )
    source_paths = {}
    for asset in ("visual", "red", "scl"):
        path = tmp_path / f"source-{asset}.tif"
        count, size = (3 if asset == "visual" else 1), (5 if asset == "scl" else 10)
        dtype = np.uint16 if asset == "red" else np.uint8
        values = np.full((count, size, size), 1500 if asset == "red" else 4, dtype=dtype)
        values[:, 1, 1] = 0
        with rio.open(
            path,
            "w",
            driver="GTiff",
            count=count,
            width=size,
            height=size,
            dtype=dtype,
            crs="EPSG:4326",
            transform=from_origin(-1, 1, 0.1 / size, 0.1 / size),
            nodata=0,
        ) as destination:
            destination.write(values)
        source_paths[asset] = path
    original_open = rio.open

    def open_source(path, *args, **kwargs):
        if str(path).startswith("https://example.test/"):
            state["raster_urls"].append(str(path))
            path = source_paths[Path(path).stem]
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(rio, "open", open_source)
    return state


def test_fresh_site_then_verified_offline_reuse(tmp_path, providers):
    cache = tmp_path / "cache"
    first = load_pv_site(**SEARCH, cache_dir=cache, name="Example PV site")
    assert len(providers["requests"]) == 2
    assert len(providers["raster_urls"]) == 3
    assert first.item["id"] == "scene-1"
    assert first.images["red"].data.shape == (1, 3, 4)
    assert first.images["scl"].data.shape == (1, 2, 2)
    assert first.images["red"].reflectance()[0, 0, 0] == pytest.approx(0.05)
    providers["requests"].clear()
    providers["raster_urls"].clear()
    second = load_pv_site(**SEARCH, cache_dir=cache, name="Example PV site", offline=True)
    assert not providers["requests"] and not providers["raster_urls"]
    for asset in first.images:
        np.testing.assert_array_equal(first.images[asset].data, second.images[asset].data)
        np.testing.assert_array_equal(first.images[asset].data.mask, second.images[asset].data.mask)
        assert first.images[asset].item_metadata == second.images[asset].item_metadata
    summary = second.summary()
    assert summary["osm_element_counts"] == {"way": 1}
    assert summary["images"]["red"]["pixel_size"] == [0.01, 0.01]
    assert json.loads(json.dumps(summary))["scene_id"] == "scene-1"


def test_only_missing_complete_asset_pair_is_retrieved(tmp_path, providers):
    load_pv_site(**SEARCH, cache_dir=tmp_path)
    (tmp_path / "site-scl.tif").unlink()
    (tmp_path / "site-scl.tif.meta.json").unlink()
    providers["requests"].clear()
    providers["raster_urls"].clear()
    site = load_pv_site(**SEARCH, cache_dir=tmp_path)
    assert not providers["requests"]
    assert providers["raster_urls"] == ["https://example.test/scene-1/scl.tif"]
    assert site.images["scl"].data.dtype == np.uint8


def test_new_scene_requires_explicit_refresh_and_does_not_overwrite_old_crops(tmp_path, providers):
    load_pv_site(**SEARCH, cache_dir=tmp_path)
    original = (tmp_path / "site-visual.tif.meta.json").read_bytes()
    providers["requests"].clear()
    providers["raster_urls"].clear()
    with pytest.raises(ValueError, match="different scene"):
        load_pv_site(**SEARCH, cache_dir=tmp_path, scene_id="scene-2")
    assert (tmp_path / "site-visual.tif.meta.json").read_bytes() == original
    assert not providers["requests"] and not providers["raster_urls"]
    refreshed = load_pv_site(**SEARCH, cache_dir=tmp_path, scene_id="scene-2", refresh=True)
    assert len(providers["requests"]) == 2 and len(providers["raster_urls"]) == 3
    assert {image.scene_id for image in refreshed.images.values()} == {"scene-2"}
    assert (
        load_pv_site(**SEARCH, cache_dir=tmp_path, scene_id="scene-2", offline=True).item["id"]
        == "scene-2"
    )


def test_tampered_cache_raises_without_provider_or_overwrite(tmp_path, providers):
    load_pv_site(**SEARCH, cache_dir=tmp_path)
    path = tmp_path / "site-visual.tif"
    damaged = path.read_bytes() + b"damaged"
    path.write_bytes(damaged)
    providers["requests"].clear()
    providers["raster_urls"].clear()
    with pytest.raises(ValueError, match="SHA-256"):
        load_pv_site(**SEARCH, cache_dir=tmp_path)
    assert path.read_bytes() == damaged
    assert not providers["requests"] and not providers["raster_urls"]


def test_changed_query_cannot_reuse_a_site_prefix(tmp_path, providers):
    load_pv_site(**SEARCH, cache_dir=tmp_path)
    providers["requests"].clear()
    changed = SEARCH.copy()
    changed["time_max"] = "2026-04-01"
    with pytest.raises(ValueError, match="different query"):
        load_pv_site(**changed, cache_dir=tmp_path)
    assert not providers["requests"]


def test_offline_preflights_all_files_before_loading_or_fetching(tmp_path, providers):
    load_pv_site(**SEARCH, cache_dir=tmp_path)
    (tmp_path / "site-scl.tif.meta.json").unlink()
    providers["requests"].clear()
    providers["raster_urls"].clear()
    with pytest.raises(FileNotFoundError, match="Offline snapshot requires"):
        load_pv_site(**SEARCH, cache_dir=tmp_path, offline=True)
    with pytest.raises(ValueError, match="Incomplete cached"):
        load_pv_site(**SEARCH, cache_dir=tmp_path)
    assert not providers["requests"] and not providers["raster_urls"]


def test_offline_blocks_http_even_if_cache_disappears_after_preflight(
    tmp_path, providers, monkeypatch
):
    load_pv_site(**SEARCH, cache_dir=tmp_path)
    providers["requests"].clear()
    factory = ground_site.Sentinel2GroundConnector

    def racing_connector(**kwargs):
        connector = factory(**kwargs)
        search = connector.search

        def lost_cache(**kwargs):
            (tmp_path / "site-scenes.json").unlink()
            return search(**kwargs)

        monkeypatch.setattr(connector, "search", lost_cache)
        return connector

    monkeypatch.setattr(ground_site, "Sentinel2GroundConnector", racing_connector)
    with pytest.raises(RuntimeError, match="forbids network requests"):
        load_pv_site(**SEARCH, cache_dir=tmp_path, offline=True)
    assert not providers["requests"]


@pytest.mark.parametrize("items,scene_id", [([], None), ([_item()], "absent")])
def test_empty_or_absent_scene_never_reads_assets_or_osm(tmp_path, providers, items, scene_id):
    providers["items"] = deepcopy(items)
    with pytest.raises(LookupError):
        load_pv_site(**SEARCH, cache_dir=tmp_path, scene_id=scene_id)
    assert len(providers["requests"]) == 1
    assert not providers["raster_urls"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"offline": True, "refresh": True},
        {"cache_prefix": "../another-site"},
        {"assets": ("../red",)},
        {"assets": "red"},
        {"assets": ("red", "red")},
        {"max_pixels": True},
        {"timeout_s": 0},
    ],
)
def test_invalid_options_fail_before_network_or_cache_mutation(tmp_path, providers, kwargs):
    cache = tmp_path / "new-cache"
    with pytest.raises(ValueError):
        load_pv_site(**SEARCH, cache_dir=cache, **kwargs)
    assert not cache.exists()
    assert not providers["requests"] and not providers["raster_urls"]


@pytest.mark.parametrize(
    "prefix,bbox,time_min,time_max,limit,scene,crs,counts",
    [
        (
            "cestas",
            (-0.833, 44.709, -0.795, 44.742),
            "2024-06-01",
            "2024-09-01",
            10,
            "S2A_T30TXQ_20240810T105747_L2A",
            "EPSG:32630",
            {"way": 23},
        ),
        (
            "rengo",
            (-70.824, -34.412, -70.808, -34.402),
            "2026-01-01",
            "2026-03-01",
            5,
            "S2C_T19HCC_20260211T144012_L2A",
            "EPSG:32719",
            {"way": 1},
        ),
    ],
)
def test_existing_real_snapshots_load_offline_unchanged(
    prefix, bbox, time_min, time_max, limit, scene, crs, counts, monkeypatch
):
    def no_http(*args, **kwargs):
        raise AssertionError("Bundled snapshots must not make an HTTP request")

    monkeypatch.setattr(httpx.Client, "send", no_http)
    site = load_pv_site(
        bbox=bbox,
        time_min=time_min,
        time_max=time_max,
        cache_dir=DATA,
        cache_prefix=prefix,
        max_cloud_cover=10,
        max_items=limit,
        offline=True,
    )
    assert site.item["id"] == scene
    assert {image.crs for image in site.images.values()} == {crs}
    assert site.images["red"].transform[0] == 10
    assert site.images["scl"].transform[0] == 20
    assert site.summary()["osm_element_counts"] == counts
