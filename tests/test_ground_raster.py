"""Ground-image tests use tiny local rasters behind mocked HTTPS asset URLs."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from space_pv_connectors import ground_raster
from space_pv_connectors.ground_raster import load_ground_image, read_ground_image

rio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402
from rasterio.warp import transform_bounds  # noqa: E402

HREF = "https://example.org/sentinel/red.tif"
BBOX = (-0.98, 0.94, -0.94, 0.97)


def _item(*, asset: str = "red", count: int = 1, reflectance: bool = True) -> dict:
    return {
        "type": "Feature",
        "id": "S2B_TEST_L2A",
        "collection": "sentinel-2-c1-l2a",
        "properties": {"datetime": "2024-06-01T10:00:00Z"},
        "assets": {
            asset: {
                "href": HREF,
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data", "reflectance"] if reflectance else ["data"],
                "raster:bands": [
                    {"scale": 0.0001, "offset": -0.1, "nodata": 0} if reflectance else {"nodata": 0}
                    for _ in range(count)
                ],
            }
        },
    }


def _raster(
    tmp_path: Path,
    *,
    pixels: np.ndarray | None = None,
    crs: str = "EPSG:4326",
    transform=None,
) -> tuple[Path, np.ndarray]:
    if pixels is None:
        pixels = np.arange(1, 101, dtype=np.uint16).reshape(1, 10, 10)
        pixels[0, 3, 2] = 0
        pixels[0, 3, 3] = 1500
    path = tmp_path / "source.tif"
    with rio.open(
        path,
        "w",
        driver="GTiff",
        count=pixels.shape[0],
        height=pixels.shape[1],
        width=pixels.shape[2],
        dtype=pixels.dtype,
        crs=crs,
        transform=transform if transform is not None else from_origin(-1, 1, 0.01, 0.01),
        nodata=0,
    ) as dst:
        dst.write(pixels)
    return path, pixels


def _route_https_to_local(monkeypatch, path: Path) -> list[dict]:
    """Map only the test asset URL to a raster and record actual read calls."""
    original_open = rio.open
    reads: list[dict] = []

    class Reader:
        def __init__(self, source):
            self.source = source

        def __getattr__(self, name):
            return getattr(self.source, name)

        def __enter__(self):
            self.source.__enter__()
            return self

        def __exit__(self, *args):
            return self.source.__exit__(*args)

        def read(self, *args, **kwargs):
            reads.append(kwargs)
            return self.source.read(*args, **kwargs)

    def open_asset(name, *args, **kwargs):
        if str(name) == HREF:
            return Reader(original_open(path, *args, **kwargs))
        return original_open(name, *args, **kwargs)

    monkeypatch.setattr(rio, "open", open_asset)
    return reads


def test_native_window_raw_values_mask_and_source_metadata(tmp_path: Path, monkeypatch) -> None:
    path, pixels = _raster(tmp_path)
    reads = _route_https_to_local(monkeypatch, path)
    item = _item()
    image = read_ground_image(item, bbox=BBOX, asset="red")
    assert image.data.shape == (1, 3, 4)
    assert image.data.dtype == np.uint16
    np.testing.assert_array_equal(image.data.data, pixels[:, 3:6, 2:6])
    assert np.ma.getmaskarray(image.data)[0, 0, 0]
    assert not np.ma.getmaskarray(image.data)[0, 0, 1]
    assert image.crs == "EPSG:4326"
    assert image.bounds == pytest.approx(BBOX)
    assert image.transform == pytest.approx((0.01, 0, -0.98, 0, -0.01, 0.97))
    assert image.bbox_wgs84 == BBOX
    assert reads[0]["masked"] is True
    assert "out_shape" not in reads[0]
    assert reads[0]["window"].width == 4
    item["assets"]["red"]["raster:bands"][0]["offset"] = 99
    assert image.asset_metadata["raster:bands"][0]["offset"] == -0.1
    assert image.item_metadata["assets"]["red"]["raster:bands"][0]["offset"] == -0.1


def test_reflectance_uses_offset_and_preserves_negative_values_and_nodata(
    tmp_path: Path, monkeypatch
) -> None:
    path, _ = _raster(tmp_path)
    _route_https_to_local(monkeypatch, path)
    image = read_ground_image(_item(), bbox=BBOX, asset="red")
    reflectance = image.reflectance()
    assert reflectance[0, 0, 1] == pytest.approx(0.05)
    assert reflectance[0, 0, 2] < 0
    assert np.ma.getmaskarray(reflectance)[0, 0, 0]
    assert image.data[0, 0, 1] == 1500


def test_window_rounds_outward_and_records_actual_pixel_bounds(tmp_path: Path, monkeypatch) -> None:
    path, _ = _raster(tmp_path)
    _route_https_to_local(monkeypatch, path)
    bbox = (-0.981, 0.941, -0.949, 0.969)
    image = read_ground_image(_item(), bbox=bbox, asset="red")
    assert image.data.shape == (1, 3, 5)
    assert image.bounds == pytest.approx((-0.99, 0.94, -0.94, 0.97))
    assert image.bbox_wgs84 == bbox


def test_projected_asset_stays_on_native_utm_grid(tmp_path: Path, monkeypatch) -> None:
    path, _ = _raster(
        tmp_path,
        crs="EPSG:32630",
        transform=from_origin(500000, 1000, 10, 10),
    )
    _route_https_to_local(monkeypatch, path)
    bbox = transform_bounds("EPSG:32630", "EPSG:4326", 500021, 941, 500059, 969)
    image = read_ground_image(_item(), bbox=bbox, asset="red")
    assert image.crs == "EPSG:32630"
    assert image.data.shape == (1, 3, 4)
    assert image.bounds == pytest.approx((500020, 940, 500060, 970))
    assert image.transform == (10, 0, 500020, 0, -10, 970)


@pytest.mark.parametrize(
    ("bbox", "message"),
    [
        ((-2, 0.94, -0.94, 0.97), "entire bbox"),
        ((-3, 2, -2, 3), "does not intersect"),
        ((170, 0, -170, 1), "antimeridian"),
        ((-181, 0, -180, 1), "bbox must satisfy"),
        ((-1, 2, 0, 1), "bbox must satisfy"),
        ((float("nan"), 0, 1, 1), "finite"),
    ],
)
def test_invalid_or_uncovered_area_never_reads_pixels(
    bbox: tuple, message: str, tmp_path: Path, monkeypatch
) -> None:
    path, _ = _raster(tmp_path)
    reads = _route_https_to_local(monkeypatch, path)
    with pytest.raises(ValueError, match=message):
        read_ground_image(_item(), bbox=bbox, asset="red")
    assert not reads


def test_limit_counts_all_bands_before_reading(tmp_path: Path, monkeypatch) -> None:
    pixels = np.ones((3, 10, 10), dtype=np.uint8)
    path, _ = _raster(tmp_path, pixels=pixels)
    reads = _route_https_to_local(monkeypatch, path)
    item = _item(asset="visual", count=3, reflectance=False)
    with pytest.raises(ValueError, match="36 band samples"):
        read_ground_image(item, bbox=BBOX, max_pixels=35)
    assert not reads
    image = read_ground_image(item, bbox=BBOX, max_pixels=36)
    assert image.data.shape == (3, 3, 4)


@pytest.mark.parametrize("maximum", [0, -1, True, 1.5])
def test_invalid_pixel_limit(maximum) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        read_ground_image(_item(), bbox=BBOX, asset="red", max_pixels=maximum)


def test_scene_classification_keeps_integer_categories(tmp_path: Path, monkeypatch) -> None:
    pixels = np.resize(np.array([0, 3, 4, 8, 11], dtype=np.uint8), (1, 10, 10))
    path, _ = _raster(tmp_path, pixels=pixels)
    _route_https_to_local(monkeypatch, path)
    image = read_ground_image(_item(asset="scl", reflectance=False), bbox=BBOX, asset="scl")
    assert image.data.dtype == np.uint8
    np.testing.assert_array_equal(image.data.data, pixels[:, 3:6, 2:6])
    assert set(image.data.compressed()) <= {3, 4, 8, 11}
    with pytest.raises(ValueError, match="reflectance role"):
        image.reflectance()


@pytest.mark.parametrize("mutation", ["missing_offset", "nan_scale", "missing_band"])
def test_reflectance_rejects_unknown_calibration(
    mutation: str, tmp_path: Path, monkeypatch
) -> None:
    path, _ = _raster(tmp_path)
    _route_https_to_local(monkeypatch, path)
    item = _item()
    bands = item["assets"]["red"]["raster:bands"]
    if mutation == "missing_offset":
        bands[0].pop("offset")
    elif mutation == "nan_scale":
        bands[0]["scale"] = float("nan")
    else:
        bands.clear()
    image = read_ground_image(item, bbox=BBOX, asset="red")
    with pytest.raises(ValueError):
        image.reflectance()


def test_geotiff_round_trip_preserves_raw_pixels_mask_crs_and_calibration(
    tmp_path: Path, monkeypatch
) -> None:
    path, _ = _raster(tmp_path)
    _route_https_to_local(monkeypatch, path)
    item = _item()
    image = read_ground_image(item, bbox=BBOX, asset="red")
    output = tmp_path / "crop.tif"
    receipt = image.save_geotiff(output)
    with rio.open(output) as saved:
        loaded = saved.read(masked=True)
        np.testing.assert_array_equal(loaded.data, image.data.data)
        np.testing.assert_array_equal(loaded.mask, image.data.mask)
        assert saved.crs.to_string() == image.crs
        assert tuple(saved.transform)[:6] == image.transform
        assert saved.scales == (0.0001,)
        assert saved.offsets == (-0.1,)
        assert saved.tags()["scene_id"] == item["id"]
    assert not Path(str(output) + ".msk").exists()
    metadata = json.loads(output.with_suffix(".tif.meta.json").read_text())
    assert metadata["stac_item"] == item
    assert metadata["scale_offset_applied"] is False
    assert metadata["cloud_mask_applied"] is False
    assert metadata["sha256"] == sha256(output.read_bytes()).hexdigest() == receipt.sha256
    assert receipt.bytes == output.stat().st_size
    restored = load_ground_image(output)
    np.testing.assert_array_equal(restored.data.data, image.data.data)
    np.testing.assert_array_equal(restored.data.mask, image.data.mask)
    np.testing.assert_array_equal(restored.reflectance(), image.reflectance())
    assert restored.asset_metadata == image.asset_metadata
    assert restored.item_metadata == image.item_metadata
    assert restored.transform == image.transform
    assert restored.bbox_wgs84 == image.bbox_wgs84
    with pytest.raises(FileExistsError):
        image.save_geotiff(output)
    image.save_geotiff(output, overwrite=True)


def test_geotiff_preserves_distinct_per_band_nodata_masks(tmp_path: Path, monkeypatch) -> None:
    pixels = np.full((3, 10, 10), 15, dtype=np.uint8)
    pixels[0, 3, 2] = 0
    pixels[1, 4, 3] = 0
    pixels[2, 5, 4] = 0
    path, _ = _raster(tmp_path, pixels=pixels)
    _route_https_to_local(monkeypatch, path)
    image = read_ground_image(_item(asset="visual", count=3, reflectance=False), bbox=BBOX)
    output = tmp_path / "rgb.tif"
    image.save_geotiff(output)
    with rio.open(output) as saved:
        np.testing.assert_array_equal(saved.read(masked=True).mask, image.data.mask)
        np.testing.assert_array_equal(saved.read(), image.data.data)
    restored = load_ground_image(output)
    np.testing.assert_array_equal(restored.data.mask, image.data.mask)
    np.testing.assert_array_equal(restored.data.data, image.data.data)


def test_cached_crop_enforces_band_sample_limit_before_reading(tmp_path: Path, monkeypatch) -> None:
    path, _ = _raster(tmp_path, pixels=np.full((3, 10, 10), 15, dtype=np.uint8))
    _route_https_to_local(monkeypatch, path)
    image = read_ground_image(_item(asset="visual", count=3, reflectance=False), bbox=BBOX)
    output = tmp_path / "saved.tif"
    image.save_geotiff(output)
    original_open = rio.open

    class NoPixelRead:
        def __init__(self, source):
            self.source = source

        def __getattr__(self, name):
            return getattr(self.source, name)

        def __enter__(self):
            self.source.__enter__()
            return self

        def __exit__(self, *args):
            return self.source.__exit__(*args)

        def read(self, *args, **kwargs):
            raise AssertionError("Pixel limit must be checked before reading")

    monkeypatch.setattr(
        rio, "open", lambda *args, **kwargs: NoPixelRead(original_open(*args, **kwargs))
    )
    with pytest.raises(ValueError, match="36 band samples"):
        load_ground_image(output, max_pixels=35)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("sha256", "0" * 64, "SHA-256"),
        ("bytes", 0, "byte count"),
        ("bounds", [1, 2, 3, 4], "grid does not match"),
        ("shape", [1, 1, 1], "grid does not match"),
        ("nodata_values", [999], "nodata does not match"),
        ("cloud_mask_applied", True, "native ground crop"),
        ("scene_id", "another-scene", "invalid source identity"),
    ],
)
def test_saved_crop_rejects_changed_provenance(
    field, value, message, tmp_path: Path, monkeypatch
) -> None:
    path, _ = _raster(tmp_path)
    _route_https_to_local(monkeypatch, path)
    output = tmp_path / "saved.tif"
    read_ground_image(_item(), bbox=BBOX, asset="red").save_geotiff(output)
    sidecar = output.with_suffix(".tif.meta.json")
    metadata = json.loads(sidecar.read_text())
    metadata[field] = value
    sidecar.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match=message):
        load_ground_image(output)


def test_saved_crop_rejects_calibration_changed_only_in_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    path, _ = _raster(tmp_path)
    _route_https_to_local(monkeypatch, path)
    output = tmp_path / "saved.tif"
    read_ground_image(_item(), bbox=BBOX, asset="red").save_geotiff(output)
    sidecar = output.with_suffix(".tif.meta.json")
    metadata = json.loads(sidecar.read_text())
    metadata["asset"]["raster:bands"][0]["offset"] = 0
    metadata["stac_item"]["assets"]["red"]["raster:bands"][0]["offset"] = 0
    sidecar.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="calibration does not match"):
        load_ground_image(output)


@pytest.mark.parametrize("suffix", [".msk", ".aux.xml"])
def test_unverified_external_raster_sidecars_cannot_override_saved_data(
    suffix: str, tmp_path: Path, monkeypatch
) -> None:
    path, _ = _raster(tmp_path)
    _route_https_to_local(monkeypatch, path)
    output = tmp_path / "saved.tif"
    read_ground_image(_item(), bbox=BBOX, asset="red").save_geotiff(output)
    Path(str(output) + suffix).write_text("not part of the saved crop checksum")
    with pytest.raises(ValueError, match="unverified external"):
        load_ground_image(output)


def test_save_does_not_silently_drop_unsupported_masks(tmp_path: Path, monkeypatch) -> None:
    pixels = np.full((3, 10, 10), 15, dtype=np.uint8)
    path, _ = _raster(tmp_path, pixels=pixels)
    _route_https_to_local(monkeypatch, path)
    image = read_ground_image(_item(asset="visual", count=3, reflectance=False), bbox=BBOX)
    mask = np.zeros(image.data.shape, dtype=bool)
    mask[0, 0, 0] = True
    changed = np.ma.array(image.data, mask=mask)
    changed_image = replace(image, data=changed)
    with pytest.raises(ValueError, match="distinct band masks losslessly"):
        changed_image.save_geotiff(tmp_path / "unsupported.tif")


@pytest.mark.parametrize(
    "href", ["/tmp/local.tif", "http://example.org/a.tif", "file:///tmp/a.tif"]
)
def test_untrusted_asset_urls_cannot_read_local_files(href: str) -> None:
    item = _item()
    item["assets"]["red"]["href"] = href
    with pytest.raises(ValueError, match="HTTPS"):
        read_ground_image(item, bbox=BBOX, asset="red")


def test_preview_is_not_mistaken_for_a_georeferenced_asset() -> None:
    item = _item()
    item["assets"]["red"]["type"] = "image/jpeg"
    with pytest.raises(ValueError, match="GeoTIFF/COG"):
        read_ground_image(item, bbox=BBOX, asset="red")


def test_missing_optional_dependency_has_actionable_error(monkeypatch) -> None:
    original_import = ground_raster.importlib.import_module

    def absent(name: str):
        if name == "rasterio":
            raise ImportError("rasterio intentionally unavailable")
        return original_import(name)

    monkeypatch.setattr(ground_raster.importlib, "import_module", absent)
    with pytest.raises(ImportError, match=r"orbital-pv\[ground\]"):
        read_ground_image(deepcopy(_item()), bbox=BBOX, asset="red")
