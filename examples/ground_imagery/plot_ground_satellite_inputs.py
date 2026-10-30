"""
Ground imagery and mapped solar-farm inputs
===========================================

Retrieve real Sentinel-2 ground images through Python and inspect the mapped
solar features used as inputs to the kind of workflow described by
`Dunnett et al. (2020) <https://doi.org/10.1038/s41597-020-0469-8>`_.
That paper builds its inventory from OpenStreetMap (OSM), not satellite-image
segmentation. The images here add visual context; this example does not run
farm clustering, settlement filtering or capacity estimation.

This walkthrough uses the Cestas solar park in France. Small, checksum-verified
real snapshots ship beside the example so documentation builds need no network.
Set ``ORBITALPV_GROUND_LIVE=1`` to fetch a separate copy through the public APIs;
the downloaded Python script also fetches data when its companion folder is
absent. Install the repository with its ``ground,examples`` extras first.

Attribution: contains modified Copernicus Sentinel data (2024), processed by
Element 84; OSM data © OpenStreetMap contributors, ODbL-1.0. See the companion
``_data/README.txt`` for source, modification and license details. The Sentinel
scene is from **10 August 2024**; the OSM snapshot is from **30 October 2026**.
This date mismatch prevents interpreting the overlay as contemporaneous labels.
"""

import json
import os
from collections import Counter
from hashlib import file_digest
from pathlib import Path
from tempfile import gettempdir

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from rasterio.plot import plotting_extent
from rasterio.warp import transform

import orbitalpv as opv

# %% Step 1 — Search public scene metadata and retain the complete STAC items
#
# Bboxes always use west/south/east/north in WGS84 longitude/latitude degrees.
# Cloud cover filters the entire scene. It does not establish cloudiness at
# this particular farm. The result cap is explicit, and source metadata stays
# available for choosing a suitable scene.

bbox = (-0.833, 44.709, -0.795, 44.742)
example_dir = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
bundled = example_dir / "_data"
live = os.environ.get("ORBITALPV_GROUND_LIVE") == "1" or not bundled.is_dir()
data_dir = Path(gettempdir()) / "orbitalpv-ground-cestas" if live else bundled
data_dir.mkdir(parents=True, exist_ok=True)

with opv.Sentinel2GroundConnector(timeout_s=60) as connector:
    scenes = connector.search(
        bbox=bbox,
        time_min="2024-06-01",
        time_max="2024-09-01",
        max_cloud_cover=10,
        max_items=10,
        cache_path=data_dir / "cestas-scenes.json",
    )
    if not scenes["features"]:
        raise RuntimeError("No matching Sentinel-2 scenes; widen the date range or cloud limit")
    item = scenes["features"][0]
    for asset in ("visual", "red", "scl"):
        destination = data_dir / f"cestas-{asset}.tif"
        if not destination.exists():
            crop = connector.read_image(item, bbox=bbox, asset=asset)
            crop.save_geotiff(destination)

print("Scene search:", scenes["context"])
print("Selected scene:", item["id"])
print("Acquired UTC:", item["properties"]["datetime"])
print("Scene-wide cloud cover (%):", item["properties"]["eo:cloud_cover"])


def read_crop(asset):
    """Read saved raw GeoTIFF pixels after checking the snapshot identity."""
    path = data_dir / f"cestas-{asset}.tif"
    metadata = json.loads(path.with_suffix(".tif.meta.json").read_text(encoding="utf-8"))
    with path.open("rb") as source:
        digest = file_digest(source, "sha256").hexdigest()
    if digest != metadata["sha256"]:
        raise ValueError(f"Crop checksum mismatch: {path}")
    if metadata["scene_id"] != item["id"] or metadata["bbox_wgs84"] != list(bbox):
        raise ValueError("Cached crop has a different scene or area; choose a new data folder")
    with rasterio.open(path) as source:
        values = source.read(masked=True)
        extent = plotting_extent(source)
        crs = source.crs.to_string()
        scales, offsets = source.scales, source.offsets
    return values, extent, crs, scales, offsets


rgb, rgb_extent, crs, _, _ = read_crop("visual")
display_rgb = np.moveaxis(rgb.filled(0), 0, -1)

fig, ax = plt.subplots(figsize=(8, 7), layout="constrained")
ax.imshow(display_rgb, extent=rgb_extent, interpolation="none")
ax.set(
    title="Step 1 — Real Sentinel-2 RGB, Cestas, 10 August 2024",
    xlabel=f"Easting [m], {crs}",
    ylabel="Northing [m]",
)
ax.ticklabel_format(style="plain", useOffset=False)
fig.supxlabel(
    "Modified Copernicus Sentinel data (2024) / Element 84 · native 10 m pixels",
    fontsize=8,
)
plt.show()

# %% Step 2 — Retrieve the paper's actual type of input: OSM energy features
#
# The connector returns raw ways and relations, with tags and original
# geometries intact. The number of objects is not the number of unique plants:
# a plant boundary and its panel groups can both appear. Plot outline segments
# separately; do not concatenate relation members into an invented polygon.

with opv.OpenStreetMapEnergyConnector(timeout_s=60) as connector:
    osm = connector.fetch_energy_features(
        bbox=bbox,
        sources=("solar",),
        cache_path=data_dir / "cestas-osm.json",
    )
print("OSM snapshot UTC:", osm.get("osm3s", {}).get("timestamp_osm_base"))
print("Raw OSM element types:", dict(Counter(element["type"] for element in osm["elements"])))

fig, ax = plt.subplots(figsize=(8, 7), layout="constrained")
ax.imshow(display_rgb, extent=rgb_extent, interpolation="none")
for element in osm["elements"]:
    plant = element.get("tags", {}).get("power") == "plant"
    color, width = ("#ffd700", 1.6) if plant else ("#00ffff", 0.7)
    if element["type"] == "node" and "lon" in element and "lat" in element:
        x, y = transform("EPSG:4326", crs, [element["lon"]], [element["lat"]])
        ax.scatter(x, y, s=8, color=color)
    geometries = [element.get("geometry", [])]
    geometries.extend(member.get("geometry", []) for member in element.get("members", []))
    for geometry in geometries:
        # Keep separate runs if an upstream geometry has a missing node.
        run = []
        for point in [*geometry, None]:
            if isinstance(point, dict) and "lon" in point and "lat" in point:
                run.append(point)
            else:
                if len(run) >= 2:
                    x, y = transform(
                        "EPSG:4326",
                        crs,
                        [p["lon"] for p in run],
                        [p["lat"] for p in run],
                    )
                    ax.plot(x, y, color=color, linewidth=width)
                run = []
ax.plot([], [], color="#ffd700", label="OSM plant outline")
ax.plot([], [], color="#00ffff", label="Other OSM solar-feature outlines")
ax.set(
    xlim=rgb_extent[:2],
    ylim=rgb_extent[2:],
    xlabel=f"Easting [m], {crs}",
    ylabel="Northing [m]",
    title="Step 2 — 2026 OSM outlines over the 2024 image",
)
ax.ticklabel_format(style="plain", useOffset=False)
ax.legend(fontsize=8, loc="upper right")
fig.supxlabel(
    "© OpenStreetMap contributors (ODbL) · outlines are not contemporaneous validation labels",
    fontsize=8,
)
plt.show()

# %% Step 3 — Keep reflectance and quality products distinct from RGB
#
# The red crop was saved as raw digital numbers. Read its preserved GeoTIFF
# scale/offset and mask before converting to reflectance. During a live read,
# ``connector.read_image(item, bbox=bbox, asset='red').reflectance()`` performs
# the same explicit conversion using STAC metadata.
#
# SCL stays on its native 20 m grid, with integer categories. We display it
# separately; resampling would be needed to mask a 10 m spectral image.
# No automatic cloud filtering or farm classification happens here.

red, red_extent, _, scales, offsets = read_crop("red")
reflectance = red[0].astype(float) * scales[0] + offsets[0]
scl, scl_extent, _, _, _ = read_crop("scl")
class_names = [
    "No data",
    "Saturated/defective",
    "Topographic shadow",
    "Cloud shadow",
    "Vegetation",
    "Not vegetated",
    "Water",
    "Unclassified",
    "Cloud: medium",
    "Cloud: high",
    "Cirrus",
    "Snow/ice",
]
class_colors = [
    "#000000",
    "#ff0000",
    "#555555",
    "#805000",
    "#008000",
    "#ffe65a",
    "#0000ff",
    "#808080",
    "#c0c0c0",
    "#ffffff",
    "#64c8ff",
    "#ff96ff",
]
fig, axes = plt.subplots(1, 2, figsize=(12, 6), layout="constrained")
im = axes[0].imshow(
    reflectance, extent=red_extent, cmap="magma", vmin=0, vmax=0.5, interpolation="none"
)
fig.colorbar(im, ax=axes[0], shrink=0.65, label="B04 surface reflectance [dimensionless]")
axes[0].set_title("Explicit red-band calibration · 10 m")
im = axes[1].imshow(
    scl[0],
    extent=scl_extent,
    cmap=ListedColormap(class_colors),
    norm=BoundaryNorm(np.arange(-0.5, 12.5), 12),
    interpolation="none",
)
present = np.unique(scl.compressed()).astype(int)
bar = fig.colorbar(im, ax=axes[1], shrink=0.65, ticks=present)
bar.ax.set_yticklabels([class_names[code] for code in present])
axes[1].set_title("Source scene classification · 20 m")
for ax in axes:
    ax.set(xlabel="Easting [m]", ylabel="Northing [m]")
    ax.ticklabel_format(style="plain", useOffset=False)
fig.suptitle("Step 3 — Native spectral data and quality classes")
plt.show()

print(
    "Red reflectance range (negative values retained):",
    float(reflectance.min()),
    float(reflectance.max()),
)
print(
    "SCL codes and pixel counts:",
    dict(zip(*np.unique(scl.compressed(), return_counts=True), strict=True)),
)
print("These inputs do not estimate panel area, installed capacity or generated power.")
