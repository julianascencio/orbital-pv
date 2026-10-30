"""
Ground imagery and mapped solar-farm inputs
===========================================

Inspect Cestas, France, with the shared PV mapping utilities. One call loads
verified Sentinel-2 crops and the original OpenStreetMap (OSM) features; the
plotting helpers produce RGB, mapped outlines and spectral-quality views.

`Dunnett et al. (2020) <https://doi.org/10.1038/s41597-020-0469-8>`_ builds its
inventory from OSM. These utilities prepare those source features and add
image context; the companion footprint and inventory examples demonstrate
image classification, farm grouping and calibrated capacity estimates.
The image is from **10 August 2024**, while the OSM snapshot is from
**30 October 2026**. The outlines are not contemporaneous validation labels.

Contains modified Copernicus Sentinel data (2024), processed by Element 84;
OSM data © OpenStreetMap contributors, ODbL-1.0.

Install the repository with its ``ground,examples`` extras. Bundled real
snapshots run offline; set ``ORBITALPV_GROUND_LIVE=1`` to fetch a separate
copy. The downloaded script also fetches when its companion folder is absent.
See ``_data/README.txt`` for provenance and data-license details.
"""

# sphinx_gallery_thumbnail_number = 2

import os
from pathlib import Path
from pprint import pprint
from tempfile import gettempdir

import matplotlib.pyplot as plt

import orbitalpv as opv

# %% Load the site once, retaining verified pixels and source features

example_dir = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
bundled = example_dir / "_data"
live = os.environ.get("ORBITALPV_GROUND_LIVE") == "1" or not bundled.is_dir()
site = opv.load_pv_site(
    name="Cestas solar park, France",
    bbox=(-0.833, 44.709, -0.795, 44.742),
    time_min="2024-06-01",
    time_max="2024-09-01",
    max_cloud_cover=10,
    max_items=10,
    cache_dir=Path(gettempdir()) / "orbitalpv-ground-cestas" if live else bundled,
    cache_prefix="cestas",
    offline=not live,
)
pprint(site.summary(), sort_dicts=False)

# %% Inspect the real RGB image on its native grid

opv.plot_pv_site(site)
plt.show()

# %% Add the original mapped solar features, with their own source date

opv.plot_pv_site(site, overlay_osm=True)
plt.show()

# %% Calibrate the red band explicitly and inspect native SCL classes
#
# The helper uses source scale/offset metadata and keeps SCL on its own grid.
# Returned figures and axes remain available for further customization.

fig, axes = opv.plot_pv_site_quality(site)
plt.show()
