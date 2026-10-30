"""
PV mapping in fewer lines: Icor, Tenerife
=========================================

Use three public utilities to retrieve and inspect a real Tenerife PV site.
ITER's `open location dataset
<https://datos.gob.es/es/catalogo/la0012321-infraestructuras-de-generacion-de-energia-en-tenerife>`_
locates Icor in Arico. Its `2019 programme
<https://www.iter.es/wp-content/uploads/2019/05/PAIF-ITER-2019-_compressed-1.pdf>`_
(page 26) documents a 2 MW ground-mounted plant. Capacity is a source record,
not a result inferred from these pixels.

The example pairs **4 August 2026** Sentinel-2 imagery with a later OSM
snapshot. Plant boundaries and mapped panel groups remain separate features;
their overlapping areas must not be summed. At 10 m, the image provides site
context, while the OSM vectors can show finer detail than the pixels.

Contains modified Copernicus Sentinel data (2026), processed by Element 84;
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
    name="Icor PV site, Arico, Tenerife",
    bbox=(-16.447, 28.192, -16.439, 28.198),
    time_min="2026-06-01",
    time_max="2026-09-01",
    max_cloud_cover=10,
    max_items=5,
    cache_dir=Path(gettempdir()) / "orbitalpv-ground-tenerife" if live else bundled,
    cache_prefix="tenerife",
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
