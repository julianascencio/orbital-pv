"""
Rinconada solar plant near Rengo, Chile
=======================================

Inspect a real solar plant in Chile using the ground imagery and OpenStreetMap
connectors. This example uses **PMGD Parque Fotovoltaico Rinconada**, in the
Rengo commune of the O'Higgins region. Chile's
`environmental registry <https://snifa.sma.gob.cl/UnidadFiscalizable/Ficha/16386>`_
identifies the site; the
`EPC project sheet <https://grupojrortiz.com/wp-content/uploads/2023/08/Planta-fotovoltaica-Rinconada.pdf>`_
records commissioning in 2019 and 8 MW nominal capacity. Those are source
records, not estimates from the imagery.

Search January and February 2026, during the Southern Hemisphere summer, then
read a small native-resolution image covering the complete mapped footprint.
The workflow retains RGB, raw red-band values, scene classification and the
original OSM features. These are inspection inputs for a mapping workflow
such as `Dunnett et al. (2020) <https://doi.org/10.1038/s41597-020-0469-8>`_;
this example does not classify panels or reproduce the paper's farm inventory.

Real, checksum-verified snapshots ship beside the example for offline builds.
Install the repository with its ``ground,examples`` extras. Set
``ORBITALPV_GROUND_LIVE=1`` to fetch a separate copy through the public APIs;
the downloaded script also fetches data when its companion folder is absent.
Acquisition and OSM snapshot dates are displayed separately because the
mapped outline is not a contemporaneous validation label.

Attribution: contains modified Copernicus Sentinel data (2026), processed by
Element 84; OSM data © OpenStreetMap contributors, ODbL-1.0. See the companion
``_data/README.txt`` for source, modification and license details.
"""

# sphinx_gallery_thumbnail_number = 2

import json
import os
from collections import Counter
from datetime import datetime
from hashlib import file_digest
from pathlib import Path
from tempfile import gettempdir

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.ticker import MaxNLocator
from rasterio.plot import plotting_extent
from rasterio.warp import transform

import orbitalpv as opv

# %% Step 1 — Find a summer image of Rinconada
#
# Bboxes use west/south/east/north in WGS84 longitude/latitude degrees.
# This roughly 1.5 km by 1.1 km area includes the complete mapped plant and
# neighbouring fields. Cloud cover describes the whole scene; inspect the
# local pixels and quality classes before deciding whether a scene is useful.

bbox = (-70.824, -34.412, -70.808, -34.402)
plant_osm_id = 829933528
example_dir = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
bundled = example_dir / "_data"
live = os.environ.get("ORBITALPV_GROUND_LIVE") == "1" or not bundled.is_dir()
data_dir = Path(gettempdir()) / "orbitalpv-ground-rengo" if live else bundled
data_dir.mkdir(parents=True, exist_ok=True)

with opv.Sentinel2GroundConnector(timeout_s=60) as connector:
    scenes = connector.search(
        bbox=bbox,
        time_min="2026-01-01",
        time_max="2026-03-01",
        max_cloud_cover=10,
        max_items=5,
        cache_path=data_dir / "rengo-scenes.json",
    )
    if not scenes["features"]:
        raise RuntimeError("No matching Sentinel-2 scenes; widen the date range or cloud limit")
    item = scenes["features"][0]
    for asset in ("visual", "red", "scl"):
        destination = data_dir / f"rengo-{asset}.tif"
        if not destination.exists():
            crop = connector.read_image(item, bbox=bbox, asset=asset)
            crop.save_geotiff(destination)

acquired = datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00"))
image_date = acquired.strftime("%d %B %Y")
print("Site: PMGD Parque Fotovoltaico Rinconada, Rengo, Chile")
print("WGS84 bbox (west, south, east, north):", bbox)
print("Scene search:", scenes["context"])
print("Selected scene:", item["id"])
print("Acquired UTC:", item["properties"]["datetime"])
print("Scene-wide cloud cover (%):", item["properties"]["eo:cloud_cover"])


def read_crop(asset):
    """Read saved raw pixels after checking the checksum, scene and area."""
    path = data_dir / f"rengo-{asset}.tif"
    metadata = json.loads(path.with_suffix(".tif.meta.json").read_text(encoding="utf-8"))
    with path.open("rb") as source:
        digest = file_digest(source, "sha256").hexdigest()
    if digest != metadata["sha256"]:
        raise ValueError(f"Crop checksum mismatch: {path}")
    if (
        metadata["scene_id"] != item["id"]
        or metadata["bbox_wgs84"] != list(bbox)
        or metadata["asset_key"] != asset
    ):
        raise ValueError(
            "Cached crop has a different scene, area or asset; choose a new data folder"
        )
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
    title=f"Rinconada solar plant near Rengo, Chile\nSentinel-2 RGB · {image_date}",
    xlabel=f"Easting [m], {crs}",
    ylabel="Northing [m]",
)
ax.ticklabel_format(style="plain", useOffset=False)
fig.supxlabel(
    f"Modified Copernicus Sentinel data ({acquired.year}) / Element 84 · native 10 m pixels",
    fontsize=8,
)
plt.show()

# %% Step 2 — Overlay the source plant boundary
#
# The selected OSM way has a photovoltaic method tag. Keep its original
# geometry and tags, including the reported capacity string. Counts describe
# raw OSM objects, not a deduplicated plant inventory. In particular, a plant
# boundary can include access roads and other land beyond the modules.

with opv.OpenStreetMapEnergyConnector(timeout_s=60) as connector:
    osm = connector.fetch_energy_features(
        bbox=bbox,
        sources=("solar",),
        cache_path=data_dir / "rengo-osm.json",
    )
osm_timestamp = osm.get("osm3s", {}).get("timestamp_osm_base", "unknown")
osm_date = osm_timestamp.partition("T")[0]
print("OSM snapshot UTC:", osm_timestamp)
print("Raw OSM element types:", dict(Counter(element["type"] for element in osm["elements"])))
mapped_plant = next(
    (
        element
        for element in osm["elements"]
        if element["type"] == "way" and element["id"] == plant_osm_id
    ),
    None,
)
if mapped_plant is None:
    print("The reference OSM way is absent from this snapshot; inspect the returned features.")
else:
    print("Rinconada OSM way:", mapped_plant["id"])
    print("Original plant tags:", mapped_plant.get("tags", {}))

fig, ax = plt.subplots(figsize=(8, 7), layout="constrained")
ax.imshow(display_rgb, extent=rgb_extent, interpolation="none")
legend_categories = set()
for element in osm["elements"]:
    plant = element.get("tags", {}).get("power") == "plant"
    color, width = ("#ffd700", 1.8) if plant else ("#00ffff", 0.8)
    label = "OSM plant boundary" if plant else "Other OSM solar features"
    if element["type"] == "node" and "lon" in element and "lat" in element:
        x, y = transform("EPSG:4326", crs, [element["lon"]], [element["lat"]])
        ax.scatter(x, y, s=12, color=color)
        legend_categories.add((color, label))
    geometries = [element.get("geometry", [])]
    geometries.extend(member.get("geometry", []) for member in element.get("members", []))
    for geometry in geometries:
        # Do not join separate relation members or runs across missing nodes.
        run = []
        for point in [*geometry, None]:
            if isinstance(point, dict) and "lon" in point and "lat" in point:
                run.append(point)
            else:
                if len(run) >= 2:
                    x, y = transform(
                        "EPSG:4326",
                        crs,
                        [point["lon"] for point in run],
                        [point["lat"] for point in run],
                    )
                    ax.plot(x, y, color=color, linewidth=width)
                    legend_categories.add((color, label))
                run = []
for color, label in sorted(legend_categories):
    ax.plot([], [], color=color, label=label)
ax.set(
    xlim=rgb_extent[:2],
    ylim=rgb_extent[2:],
    xlabel=f"Easting [m], {crs}",
    ylabel="Northing [m]",
    title=f"Rinconada: satellite image and mapped boundary\nImage {acquired.date()} · OSM {osm_date}",
)
ax.ticklabel_format(style="plain", useOffset=False)
if legend_categories:
    ax.legend(fontsize=8, loc="upper right")
fig.supxlabel(
    f"Modified Copernicus Sentinel data ({acquired.year}) / Element 84\n"
    "© OpenStreetMap contributors (ODbL) · image and map dates differ",
    fontsize=8,
)
plt.show()

# %% Step 3 — Inspect calibrated spectral data and native quality classes
#
# Apply the saved red band's scale and offset explicitly, after masking
# nodata. A live ``connector.read_image(item, bbox=bbox, asset='red')`` also
# exposes ``.reflectance()`` for this conversion using the STAC metadata.
#
# SCL remains on its own 20 m grid. Its categories are not panel labels and
# are not automatically applied to the 10 m image. Neither display enlarging
# nor resampling creates information about individual modules.

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
fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
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
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
fig.suptitle(f"Rinconada · {image_date} · {crs}")
fig.supxlabel(
    f"Modified Copernicus Sentinel data ({acquired.year}) / Element 84 · no resampling",
    fontsize=8,
)
plt.show()

print(
    "Red reflectance range (negative values retained):",
    float(reflectance.min()),
    float(reflectance.max()),
)
codes, counts = np.unique(scl.compressed(), return_counts=True)
print("SCL codes and pixel counts:", dict(zip(codes.tolist(), counts.tolist(), strict=True)))
print("Plant capacity is a source tag; these images do not estimate capacity or generated power.")
