from __future__ import annotations

import importlib
import io
import json
import zipfile
from dataclasses import replace
from hashlib import sha256

import httpx
import numpy as np
import pytest

from space_pv_connectors.ground_ghsl import (
    GHSLSettlementConnector,
    SettlementRaster,
    load_settlement_raster,
)

rio = pytest.importorskip("rasterio")
Affine = importlib.import_module("rasterio.transform").Affine
transform = importlib.import_module("rasterio.warp").transform

BBOX = (-0.01, -0.01, 0.01, 0.01)
PRODUCT = "GHS_SMOD_E2015_GLOBE_R2023A_54009_1000_V2_0"


def _raster(path, *, crs="ESRI:54009", pixel_size=1000):
    data = np.full((8, 8), 11, dtype=np.int16)
    data[2:4, 2:4] = 30
    data[4:6, 2:4] = 10
    data[4, 4] = -200
    with rio.open(
        path,
        "w",
        driver="GTiff",
        count=1,
        width=8,
        height=8,
        dtype="int16",
        crs=crs,
        transform=Affine(pixel_size, 0, -4000, 0, -pixel_size, 4000),
        nodata=-200,
    ) as dst:
        dst.write(data, 1)
    return data


def _archive(tmp_path, *, member=PRODUCT + ".tif"):
    source = tmp_path / "source.tif"
    _raster(source)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr(member, source.read_bytes())
    return stream.getvalue()


def _connector(handler):
    connector = GHSLSettlementConnector()
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(handler))
    return connector


def _no_http(request):
    raise AssertionError(f"Unexpected HTTP request: {request.url}")


def test_native_download_crop_cache_and_offline_roundtrip(tmp_path):
    archive = _archive(tmp_path)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=archive)

    cache = tmp_path / "icor.tif"
    with _connector(handler) as connector:
        result = connector.fetch_settlement(bbox=BBOX, cache_path=cache)
        reused = connector.fetch_settlement(bbox=BBOX, cache_path=cache)
    assert len(requests) == 1
    assert "R2023A" in str(requests[0].url)
    assert result.transform[0] == 1000
    assert result.transform[4] == -1000
    assert result.edition == "R2023A" and result.epoch == 2015
    assert result.provenance["archive_sha256"] == sha256(archive).hexdigest()
    assert result.provenance["paper_input_edition"] is False
    assert result.provenance["historical_epoch_not_current_land_cover"] is True
    np.testing.assert_array_equal(result.data.data, reused.data.data)
    np.testing.assert_array_equal(result.data.mask, reused.data.mask)
    with _connector(_no_http) as connector:
        offline = connector.fetch_settlement(bbox=BBOX, cache_path=cache, offline=True)
    np.testing.assert_array_equal(offline.data.mask, result.data.mask)


def test_explicit_local_historical_source(tmp_path):
    source = tmp_path / "historic.tif"
    _raster(source)
    with _connector(_no_http) as connector:
        result = connector.fetch_settlement(
            bbox=BBOX,
            cache_path=tmp_path / "crop.tif",
            source_path=source,
            edition="R2019A",
            offline=True,
        )
    assert result.provenance["paper_input_edition"] is True
    assert result.provenance["edition_epoch_declared_by_caller"] is True
    assert result.provenance["source_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert result.edition == "R2019A"


def test_historical_edition_never_substituted(tmp_path):
    with _connector(_no_http) as connector, pytest.raises(FileNotFoundError, match="R2019A"):
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "crop.tif", edition="R2019A")


def test_missing_offline_source_is_explicit(tmp_path):
    with _connector(_no_http) as connector, pytest.raises(FileNotFoundError, match="offline"):
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "crop.tif", offline=True)


def test_class_flags_and_unknowns_are_not_false(tmp_path):
    mask = np.zeros((3, 4), dtype=bool)
    mask[2, 2] = True
    data = np.ma.array(
        [[10, 11, 12, 13], [21, 22, 23, 30], [0, 99, 30, 11]], mask=mask, dtype=np.int16
    )
    layer = SettlementRaster(
        data=data,
        crs="ESRI:54009",
        transform=(1000, 0, 0, 0, -1000, 3000),
        bounds=(0, 0, 4000, 3000),
        bbox_wgs84=(-1, -1, 1, 1),
        epoch=2015,
        edition="R2023A",
        provenance={"source": "test fixture"},
    )
    xs = [500 + 1000 * col for row in range(3) for col in range(4)]
    ys = [2500 - 1000 * row for row in range(3) for col in range(4)]
    lons, lats = transform(layer.crs, "EPSG:4326", xs, ys)
    results = layer.sample_points(list(zip(lons, lats, strict=True)))
    assert [r["urban"] for r in results[:8]] == [False] * 4 + [True] * 4
    assert [r["water"] for r in results[:8]] == [True] + [False] * 7
    assert results[8]["status"] == "unknown_class"
    assert results[9]["class_code"] == 99
    assert results[9]["urban"] is None and results[9]["water"] is None
    assert results[10]["status"] == "nodata" and results[10]["class_code"] is None
    assert layer.sample_points([(180, 0)])[0]["status"] == "outside_crop"
    assert layer.sample_points([]) == []
    cache = tmp_path / "snapshot.tif"
    layer.save(cache)
    np.testing.assert_array_equal(load_settlement_raster(cache).data.mask, layer.data.mask)


@pytest.mark.parametrize("point", [[1], [[180.1, 0]], [[0, 90.1]], [[np.nan, 1]]])
def test_invalid_point_coordinates(point):
    layer = SettlementRaster(
        np.ma.array([[11]]),
        "ESRI:54009",
        (1000, 0, 0, 0, -1000, 1000),
        (0, 0, 1000, 1000),
        BBOX,
        2015,
        "R2023A",
        {},
    )
    with pytest.raises(ValueError, match="longitude"):
        layer.sample_points(point)


def test_query_identity_and_tamper_detection(tmp_path):
    source = tmp_path / "source.tif"
    _raster(source)
    cache = tmp_path / "crop.tif"
    with _connector(_no_http) as connector:
        connector.fetch_settlement(bbox=BBOX, cache_path=cache, source_path=source)
        with pytest.raises(ValueError, match="different request"):
            connector.fetch_settlement(
                bbox=(-0.02, -0.02, 0.02, 0.02), cache_path=cache, source_path=source
            )
    cache.write_bytes(cache.read_bytes() + b"modified")
    with pytest.raises(ValueError, match="checksum"):
        load_settlement_raster(cache)


def test_source_cache_integrity(tmp_path):
    content = _archive(tmp_path)
    with _connector(lambda r: httpx.Response(200, content=content)) as connector:
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "first.tif")
    archive = tmp_path / "ghsl_source" / f"{PRODUCT}.zip"
    archive.write_bytes(archive.read_bytes() + b"tampered")
    with _connector(_no_http) as connector, pytest.raises(ValueError, match="checksum"):
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "second.tif")


@pytest.mark.parametrize("headers", [{"content-length": "1000000"}, {}])
def test_download_size_limits_before_and_during_read(tmp_path, headers):
    archive = _archive(tmp_path)
    with (
        _connector(
            lambda r: httpx.Response(200, stream=httpx.ByteStream(archive), headers=headers)
        ) as connector,
        pytest.raises(ValueError, match="max_download_bytes"),
    ):
        connector.fetch_settlement(
            bbox=BBOX, cache_path=tmp_path / "crop.tif", max_download_bytes=20
        )
    assert not (tmp_path / "crop.tif").exists()
    assert not list((tmp_path / "ghsl_source").glob("*.zip"))


def test_provider_failure_is_not_an_empty_settlement_map(tmp_path):
    with (
        _connector(lambda r: httpx.Response(503, content=b"unavailable")) as connector,
        pytest.raises(httpx.HTTPStatusError),
    ):
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "crop.tif")
    assert not (tmp_path / "crop.tif").exists()


def test_existing_archive_can_supply_new_crop_offline(tmp_path):
    archive = _archive(tmp_path)
    with _connector(lambda r: httpx.Response(200, content=archive)) as connector:
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "first.tif")
    with _connector(_no_http) as connector:
        result = connector.fetch_settlement(
            bbox=(-0.02, -0.02, 0.02, 0.02),
            cache_path=tmp_path / "second.tif",
            offline=True,
        )
    assert result.data.shape[0] >= 4 and result.data.shape[1] >= 4


@pytest.mark.parametrize("member", ["../source.tif", "wrong.tif"])
def test_archive_member_identity_is_strict(tmp_path, member):
    archive = _archive(tmp_path, member=member)
    with (
        _connector(lambda r: httpx.Response(200, content=archive)) as connector,
        pytest.raises(ValueError, match="expected GeoTIFF"),
    ):
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "crop.tif")
    assert not (tmp_path / "crop.tif").exists()


def test_sample_limit_and_native_grid_are_enforced(tmp_path):
    source = tmp_path / "source.tif"
    _raster(source)
    with _connector(_no_http) as connector:
        with pytest.raises(ValueError, match="max_pixels"):
            connector.fetch_settlement(
                bbox=BBOX, cache_path=tmp_path / "crop.tif", source_path=source, max_pixels=1
            )
        with pytest.raises(ValueError, match="complete requested bbox"):
            connector.fetch_settlement(
                bbox=(-10, -10, 10, 10), cache_path=tmp_path / "crop.tif", source_path=source
            )
        _raster(source, pixel_size=500)
        with pytest.raises(ValueError, match="native"):
            connector.fetch_settlement(
                bbox=BBOX, cache_path=tmp_path / "crop.tif", source_path=source
            )


def test_snapshot_grid_and_external_mask_are_verified(tmp_path):
    source = tmp_path / "source.tif"
    _raster(source)
    cache = tmp_path / "crop.tif"
    with _connector(_no_http) as connector:
        connector.fetch_settlement(bbox=BBOX, cache_path=cache, source_path=source)
    with pytest.raises(ValueError, match="max_pixels"):
        load_settlement_raster(cache, max_pixels=1)
    sidecar = cache.with_suffix(".tif.meta.json")
    metadata = json.loads(sidecar.read_text())
    metadata["transform"][0] = 999
    sidecar.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="does not match"):
        load_settlement_raster(cache)
    cache.with_suffix(".tif.msk").touch()
    with pytest.raises(ValueError, match="external"):
        load_settlement_raster(cache)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"epoch": 2016},
        {"epoch": True},
        {"edition": "R2016A"},
        {"max_pixels": 0},
        {"max_download_bytes": 0},
        {"offline": True, "refresh": True},
    ],
)
def test_invalid_queries(kwargs, tmp_path):
    with _connector(_no_http) as connector, pytest.raises(ValueError):
        connector.fetch_settlement(bbox=BBOX, cache_path=tmp_path / "crop.tif", **kwargs)


def test_save_does_not_overwrite_without_explicit_flag(tmp_path):
    source = tmp_path / "source.tif"
    _raster(source)
    cache = tmp_path / "crop.tif"
    with _connector(_no_http) as connector:
        raster = connector.fetch_settlement(bbox=BBOX, cache_path=cache, source_path=source)
    with pytest.raises(FileExistsError):
        raster.save(cache)
    replace(raster, data=raster.data.copy()).save(cache, overwrite=True)
    assert load_settlement_raster(cache).epoch == 2015


def _manual_layer(**changes):
    fields = {
        "data": np.ma.array([[30]], dtype=np.int16),
        "crs": "ESRI:54009",
        "transform": (1000, 0, 0, 0, -1000, 1000),
        "bounds": (0, 0, 1000, 1000),
        "bbox_wgs84": BBOX,
        "epoch": 2015,
        "edition": "R2023A",
        "provenance": {"source": "explicit test fixture"},
    }
    fields.update(changes)
    return SettlementRaster(**fields)


@pytest.mark.parametrize(
    "changes",
    [
        {"data": np.ma.array([[30.5]])},
        {"data": np.ma.array([[True]])},
        {"data": np.ma.array([30])},
        {"data": np.ma.array(np.zeros((0, 1), dtype=np.int16))},
        {"crs": "EPSG:4326"},
        {"transform": (1000, 1, 0, 0, -1000, 1000)},
        {"transform": (500, 0, 0, 0, -500, 1000)},
        {"transform": (1000, 0, np.nan, 0, -1000, 1000)},
        {"transform": (1000, 0, 0, 0, -1000)},
        {"bounds": (0, 0, 1000, np.inf)},
        {"bounds": (0, 0, 2000, 1000)},
        {"epoch": 2016},
        {"edition": "R2016A"},
        {"provenance": {"value": np.nan}},
    ],
)
def test_manual_layers_reject_false_native_grid_claims(changes):
    with pytest.raises(ValueError):
        _manual_layer(**changes)


@pytest.mark.parametrize("operation", ["sample", "save"])
def test_mutated_mask_is_revalidated_at_use(tmp_path, operation):
    layer = _manual_layer()
    object.__setattr__(layer.data, "_mask", np.array([[2]], dtype=np.int8))
    with pytest.raises(ValueError, match="mask must be boolean"):
        if operation == "sample":
            layer.sample_points([(0, 0)])
        else:
            layer.save(tmp_path / "invalid.tif")
    assert not (tmp_path / "invalid.tif").exists()


def test_unknown_integer_codes_are_still_allowed():
    layer = _manual_layer(data=np.ma.array([[99]], dtype=np.int16))
    lons, lats = transform(layer.crs, "EPSG:4326", [500], [500])
    result = layer.sample_points([(lons[0], lats[0])])[0]
    assert result["class_code"] == 99
    assert result["status"] == "unknown_class"
    assert result["urban"] is None and result["water"] is None
