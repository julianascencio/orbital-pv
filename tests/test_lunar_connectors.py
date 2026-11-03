from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import numpy as np
import pytest

from orbitalpv import lunar

DATA = Path(__file__).resolve().parents[1] / "examples/lunar/_data"


def client(connector, handler):
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return connector


def test_lola_download_cache_and_checksum(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=b"test raster bytes")

    with client(lunar.LolaConnector(), handler) as connector:
        first = connector.site_dem("01", tmp_path / "site.tif")
        second = connector.site_dem("01", tmp_path / "site.tif")
        assert first.sha256 == second.sha256 == hashlib.sha256(b"test raster bytes").hexdigest()
        assert len(calls) == 1
        with pytest.raises(ValueError, match="different product"):
            connector.site_dem("04", tmp_path / "site.tif")
        (tmp_path / "site.tif").write_bytes(b"corrupt")
        with pytest.raises(ValueError, match="checksum"):
            connector.site_dem("01", tmp_path / "site.tif")
        connector.site_dem("01", tmp_path / "site.tif", refresh=True)
        connector.site_dem("11", tmp_path / "error.tif", height_error=True)
        assert calls[-1].endswith("Site11_final_adj_5mpp_toterr.tif")
        with pytest.raises(ValueError):
            connector.site_dem("../../bad", tmp_path / "bad")


def test_html_and_http_errors_are_not_cached(tmp_path):
    with (
        client(
            lunar.LolaConnector(),
            lambda r: httpx.Response(
                200, text="maintenance", headers={"Content-Type": "text/html"}
            ),
        ) as connector,
        pytest.raises(ValueError, match="HTML"),
    ):
        connector.polar_dem(tmp_path / "bad.tif")
    assert not (tmp_path / "bad.tif").exists()
    with (
        client(lunar.LolaConnector(), lambda r: httpx.Response(404)) as connector,
        pytest.raises(httpx.HTTPStatusError),
    ):
        connector.polar_dem(tmp_path / "bad.tif")


def test_diviner_requests_include_label_and_bounded_bin(tmp_path):
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200, content=b"source")

    with client(lunar.DivinerConnector(), handler) as connector:
        data, label = connector.seasonal_temperature(24, tmp_path)
        assert data.url.endswith("slon24_240.tab")
        assert label.url.endswith("slon24_240.xml")
        assert len(urls) == 2
        with pytest.raises(ValueError):
            connector.seasonal_temperature(25, tmp_path)


def test_real_diviner_labelled_subset_and_missing_values():
    content, label = (
        (DATA / "diviner_subset.tab").read_bytes(),
        (DATA / "diviner_label.xml").read_bytes(),
    )
    data = lunar.parse_diviner_pcp(content, label, allow_subset=True)
    assert len(data) > 300
    assert data.temperature_k.between(0, 400).all()
    assert data.latitude_deg.between(-90, -88).all()
    assert data.attrs["original_records"] == 3_176_166
    with pytest.raises(ValueError, match="record count"):
        lunar.parse_diviner_pcp(content, label)
    modified = bytearray(content)
    modified[68 + 56 : 68 + 66] = b"     -9999"
    missing = lunar.parse_diviner_pcp(bytes(modified), label, allow_subset=True)
    assert np.isnan(missing.temperature_k.iloc[0])
    with pytest.raises(ValueError, match="Truncated"):
        lunar.parse_diviner_pcp(content[:-6], label, allow_subset=True)
    with pytest.raises(ValueError, match="columns"):
        lunar.parse_diviner_pcp(
            content, label.replace(b"<name>tbol</name>", b"<name>wrong</name>"), allow_subset=True
        )


def test_spice_kernel_manifest_and_no_pool_mutation(tmp_path, monkeypatch):
    import spiceypy

    def forbidden(*args):
        raise AssertionError("Downloader must not mutate SPICE state")

    monkeypatch.setattr(spiceypy, "furnsh", forbidden)
    monkeypatch.setattr(spiceypy, "kclear", forbidden)
    with client(
        lunar.LunarSpiceConnector(), lambda r: httpx.Response(200, content=b"kernel")
    ) as connector:
        receipts = connector.download(tmp_path)
        assert len(receipts) == 4
        assert {Path(r.path).name for r in receipts} == set(connector.KERNELS)
        assert all(Path(r.path).exists() for r in receipts)


def test_svs_metadata_and_reference_image(tmp_path):
    def handler(request):
        if request.url.path == "/api/4930":
            return httpx.Response(
                200, json={"id": 4930, "title": "Lunar illumination", "media_groups": []}
            )
        return httpx.Response(200, content=b"image")

    with client(lunar.LunarIlluminationConnector(), handler) as connector:
        response = connector.metadata(cache_path=tmp_path / "svs.json")
        assert response.data["id"] == 4930
        assert connector.reference_image(2026, tmp_path / "svs.jpg").url.endswith(
            "sp_illum_2026_print.jpg"
        )
        with pytest.raises(ValueError):
            connector.reference_image(2031, tmp_path / "bad")
        with pytest.raises(ValueError):
            connector.frame(2026, "../bad.png", tmp_path / "bad")


def test_offline_inputs_checksums_and_terrain_consistency():
    manifest = json.loads((DATA / "provenance.json").read_text())
    assert manifest["frame"] == lunar.LUNAR_FRAME
    for name, info in manifest["files"].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == info["sha256"]
    with np.load(DATA / "site01_5m.npz", allow_pickle=False) as data:
        terrain = lunar.LunarTerrain(data["x_m"], data["y_m"], data["elevation_m"])
    assert np.diff(terrain.x_m)[0] == 5
    assert np.diff(terrain.y_m)[0] == 5
    assert terrain.elevation_m.min() > -5000


def test_geotiff_projection_nodata_and_bounds(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    path = tmp_path / "moon.tif"
    crs = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="float32",
        crs=crs,
        transform=from_origin(-10, 10, 5, 5),
        nodata=-9999,
    ) as ds:
        array = np.arange(16, dtype=np.float32).reshape(4, 4)
        array[0, 0] = -9999
        ds.write(array, 1)
    t = lunar.read_lola_geotiff(path)
    np.testing.assert_allclose(t.y_m, [-7.5, -2.5, 2.5, 7.5])
    assert np.isnan(t.elevation_m[-1, 0])
    assert t.elevation_m[0, 0] == 12
    subset = lunar.read_lola_geotiff(path, bounds_m=(-5, -5, 5, 5))
    assert subset.elevation_m.shape == (2, 2)
    with pytest.raises(ValueError, match="outside"):
        lunar.read_lola_geotiff(path, bounds_m=(-20, -5, 5, 5))


def test_ephemeris_requires_increasing_explicit_utc():
    with pytest.raises(ValueError, match="UTC"):
        lunar.lunar_ephemeris(["2026-01-01", "2026-01-02"])
