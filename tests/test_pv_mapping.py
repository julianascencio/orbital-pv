"""Plotting checks exercise coordinates, source masks and native image grids."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from space_pv_connectors.ground_raster import GroundImage
from space_pv_connectors.ground_site import PVSite

matplotlib = pytest.importorskip("matplotlib")
pytest.importorskip("rasterio")
matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from orbitalpv import mapping  # noqa: E402

BBOX = (0.0, 0.0, 0.0003, 0.0003)
SCENE_ID = "S2_TEST"
ITEM = {"id": SCENE_ID, "properties": {"datetime": "2026-02-11T14:52:20Z"}}


def _image(asset: str, values, *, transform=(10, 0, 0, 0, -10, 40)) -> GroundImage:
    data = np.ma.array(values)
    height, width = data.shape[-2:]
    a, _, left, _, e, top = transform
    metadata = {"roles": ["data"]}
    if asset == "red":
        metadata = {
            "roles": ["data", "reflectance"],
            "raster:bands": [{"scale": 0.0001, "offset": -0.1}],
        }
    return GroundImage(
        data=data,
        crs="EPSG:3857",
        transform=transform,
        bounds=(left, top + e * height, left + a * width, top),
        scene_id=SCENE_ID,
        asset_key=asset,
        source_url=f"https://example.org/{asset}.tif",
        asset_metadata=metadata,
        bbox_wgs84=BBOX,
        item_metadata=ITEM,
        nodata_values=(0,) * data.shape[0],
        retrieved_at="2026-10-30T10:00:00Z",
    )


@pytest.fixture
def site() -> PVSite:
    visual_mask = np.zeros((3, 4, 4), dtype=bool)
    visual_mask[0, 0, 0] = True
    visual = np.ma.array(np.full((3, 4, 4), 100, dtype=np.uint8), mask=visual_mask)
    red_mask = np.zeros((1, 4, 4), dtype=bool)
    red_mask[0, 0, 0] = True
    red_values = np.full((1, 4, 4), 1500, dtype=np.uint16)
    red_values[0, 0, :3] = (0, 999, 8000)
    red = np.ma.array(red_values, mask=red_mask)
    scl_mask = np.zeros((1, 3, 3), dtype=bool)
    scl_mask[0, -1, -1] = True
    scl = np.ma.array([[[4, 5, 7], [4, 5, 7], [4, 5, 0]]], dtype=np.uint8, mask=scl_mask)
    return PVSite(
        name="Test PV site",
        bbox_wgs84=BBOX,
        scenes={"features": [ITEM]},
        item=ITEM,
        images={
            "visual": _image("visual", visual),
            "red": _image("red", red),
            "scl": _image("scl", scl, transform=(20, 0, 0, 0, -20, 60)),
        },
        osm={"elements": [], "osm3s": {"timestamp_osm_base": "2026-10-30T10:00:00Z"}},
    )


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def test_rgb_reuses_axes_and_preserves_source_values_mask_and_extent(site) -> None:
    before = site.images["visual"].data.copy()
    _, ax = plt.subplots()
    returned = mapping.plot_pv_site(site, ax=ax)
    assert returned is ax
    image = ax.images[0]
    assert tuple(image.get_extent()) == (0, 40, 0, 40)
    assert image.get_interpolation() == "none"
    displayed = image.get_array()
    assert displayed is not None
    assert displayed.shape == (4, 4, 3)
    assert displayed[0, 0, 0] == 0
    np.testing.assert_array_equal(site.images["visual"].data.data, before.data)
    np.testing.assert_array_equal(site.images["visual"].data.mask, before.mask)
    assert "11 February 2026" in ax.get_title()
    assert "EPSG:3857" in ax.get_xlabel()
    assert any("native 10 m" in text.get_text() for text in ax.texts)


def test_supplied_axes_keep_separate_acquisition_attributions_and_figure_credits(site) -> None:
    figure, axes = plt.subplots(1, 2, layout="constrained")
    credits = figure.supxlabel("Caller-provided credits")
    older_item = {"id": "OLDER", "properties": {"datetime": "2024-08-10T10:00:00Z"}}
    older = replace(
        site,
        item=older_item,
        images={
            name: replace(image, scene_id="OLDER", item_metadata=older_item)
            for name, image in site.images.items()
        },
    )
    mapping.plot_pv_site(older, ax=axes[0])
    mapping.plot_pv_site(site, ax=axes[1])
    assert credits.get_text() == "Caller-provided credits"
    assert any("data (2024)" in text.get_text() for text in axes[0].texts)
    assert any("data (2026)" in text.get_text() for text in axes[1].texts)


def test_overlay_projects_wgs84_coordinates_and_labels_only_drawn_features(site) -> None:
    site.osm["elements"] = [
        {
            "type": "way",
            "id": 1,
            "tags": {"power": "plant"},
            "geometry": [{"lon": 0, "lat": 0}, {"lon": 0.0001, "lat": 0.0002}],
        }
    ]
    ax = mapping.plot_pv_site(site, overlay_osm=True)
    assert len(ax.lines) == 1
    # Known Web Mercator metres, rather than the source's tiny degree values.
    np.testing.assert_allclose(np.asarray(ax.lines[0].get_xdata()), [0, 11.1319490793], atol=1e-8)
    np.testing.assert_allclose(np.asarray(ax.lines[0].get_ydata()), [0, 22.2638981587], atol=1e-8)
    assert ax.get_xlim() == (0, 40)
    assert ax.get_ylim() == (0, 40)
    legend = ax.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.texts] == ["OSM plant outlines"]
    assert "Image 2026-02-11 · OSM 2026-10-30" in ax.get_title()
    assert any("OpenStreetMap" in text.get_text() for text in ax.figure.texts)


def test_relation_members_and_missing_nodes_are_separate_lines(site) -> None:
    points = [{"lon": value / 100000, "lat": 0} for value in range(6)]
    site.osm["elements"] = [
        {
            "type": "relation",
            "id": 1,
            "tags": {"power": "plant"},
            "members": [
                {"type": "way", "geometry": [*points[:2], None, *points[2:4]]},
                {"type": "way", "geometry": points[4:]},
                {"type": "node", "lon": 0.0001, "lat": 0.0001},
            ],
        }
    ]
    ax = mapping.plot_pv_site(site, overlay_osm=True)
    assert [len(np.asarray(line.get_xdata())) for line in ax.lines] == [2, 2, 2]
    assert len(ax.collections) == 1
    legend = ax.get_legend()
    assert legend is not None
    labels = [text.get_text() for text in legend.texts]
    assert labels == ["OSM plant outlines", "OSM plant locations"]
    assert np.asarray(ax.lines[0].get_xdata())[-1] < np.asarray(ax.lines[1].get_xdata())[0]


def test_invalid_points_split_geometry_instead_of_joining_across_gaps(site) -> None:
    site.osm["elements"] = [
        {
            "type": "way",
            "id": 1,
            "geometry": [
                {"lon": 0, "lat": 0},
                {"lon": 0.0001, "lat": 0},
                {"lon": float("nan"), "lat": 0},
                {"lon": 0.0002, "lat": 0},
                {"lon": 0.0003, "lat": 0},
            ],
        }
    ]
    ax = mapping.plot_pv_site(site, overlay_osm=True)
    assert [len(np.asarray(line.get_xdata())) for line in ax.lines] == [2, 2]
    legend = ax.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.texts] == ["OSM solar-feature outlines"]


@pytest.mark.parametrize(
    ("elements", "message"),
    [
        ([], "No mapped solar features returned"),
        ([{"type": "way", "id": 1}], "No drawable OSM geometry"),
    ],
)
def test_empty_or_unavailable_osm_geometry_is_reported_without_fake_legend(
    site, elements, message
) -> None:
    site.osm["elements"] = elements
    ax = mapping.plot_pv_site(site, overlay_osm=True)
    assert ax.get_legend() is None
    assert not ax.lines
    assert any(text.get_text() == message for text in ax.texts)


def test_quality_preserves_calibrated_negative_values_masks_and_distinct_grids(site) -> None:
    before = site.images["red"].data.copy()
    figure, axes = mapping.plot_pv_site_quality(site)
    assert len(axes) == 2
    assert all(ax.figure is figure for ax in axes)
    red_values = axes[0].images[0].get_array()
    assert red_values.shape == (4, 4)
    assert red_values.mask[0, 0]
    assert red_values[0, 1] == pytest.approx(-0.0001)
    assert red_values[0, 2] == pytest.approx(0.7)
    assert axes[0].images[0].colorbar.extend == "both"
    assert tuple(axes[0].images[0].get_extent()) == (0, 40, 0, 40)
    assert tuple(axes[1].images[0].get_extent()) == (0, 60, 0, 60)
    assert axes[1].images[0].get_array().shape == (3, 3)
    assert axes[1].images[0].get_array().mask[-1, -1]
    np.testing.assert_array_equal(before.data, site.images["red"].data.data)
    np.testing.assert_array_equal(before.mask, site.images["red"].data.mask)
    assert "10 m" in axes[0].get_title()
    assert "20 m" in axes[1].get_title()
    bar = axes[1].images[0].colorbar
    assert [text.get_text() for text in bar.ax.get_yticklabels()] == [
        "Vegetation",
        "Not vegetated",
        "Unclassified",
    ]


@pytest.mark.parametrize("values", [np.array([[[12]]], dtype=np.uint8), np.array([[[4.5]]])])
def test_invalid_scl_categories_raise_instead_of_becoming_other_classes(site, values) -> None:
    site.images["scl"] = _image("scl", values)
    with pytest.raises(ValueError, match="integer category codes"):
        mapping.plot_pv_site_quality(site)


def test_geographic_image_has_degree_labels_and_its_actual_pixel_size(site) -> None:
    image = site.images["visual"]
    site.images["visual"] = replace(
        image,
        crs="EPSG:4326",
        transform=(0.001, 0, 0, 0, -0.001, 0.004),
        bounds=(0, 0, 0.004, 0.004),
    )
    ax = mapping.plot_pv_site(site)
    assert "Longitude [°]" in ax.get_xlabel()
    assert "Latitude [°]" in ax.get_ylabel()
    assert any("native 0.001 ° pixels" in text.get_text() for text in ax.figure.texts)


def test_missing_required_asset_and_wrong_scene_are_clear_errors(site) -> None:
    visual = site.images.pop("visual")
    with pytest.raises(ValueError, match="requires the 'visual' asset"):
        mapping.plot_pv_site(site)
    site.images["visual"] = replace(visual, scene_id="OTHER_SCENE")
    with pytest.raises(ValueError, match="selected scene"):
        mapping.plot_pv_site(site)


@pytest.mark.parametrize("missing", ["matplotlib", "rasterio"])
def test_missing_optional_dependency_has_install_guidance(site, monkeypatch, missing) -> None:
    original = mapping.importlib.import_module

    def import_module(name):
        if name.split(".")[0] == missing:
            raise ImportError(f"{missing} unavailable")
        return original(name)

    monkeypatch.setattr(mapping.importlib, "import_module", import_module)
    with pytest.raises(ImportError, match=r"orbital-pv\[ground,examples\]"):
        mapping.plot_pv_site(site)


def test_mapping_import_does_not_load_matplotlib_or_rasterio() -> None:
    code = """
import importlib.abc
import sys

class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'matplotlib', 'rasterio'}:
            raise ImportError('Optional dependency imported eagerly: ' + fullname)

sys.meta_path.insert(0, BlockOptional())
import orbitalpv.mapping
assert 'matplotlib' not in sys.modules
assert 'rasterio' not in sys.modules
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(str(Path(path).resolve()) for path in sys.path if path)
    subprocess.run(
        [sys.executable, "-c", code], env=env, check=True, capture_output=True, text=True
    )
