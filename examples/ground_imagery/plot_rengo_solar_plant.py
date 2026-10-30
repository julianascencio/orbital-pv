"""
Rinconada solar plant near Rengo, Chile
=======================================

Map PMGD Parque Fotovoltaico Rinconada using the same utilities as the Cestas
and Tenerife examples. Chile's
`environmental registry <https://snifa.sma.gob.cl/UnidadFiscalizable/Ficha/16386>`_
identifies the site, and the
`EPC project sheet <https://grupojrortiz.com/wp-content/uploads/2023/08/Planta-fotovoltaica-Rinconada.pdf>`_
records commissioning in 2019 and 8 MW nominal capacity. These are source
records, not image-derived estimates.

The Southern Hemisphere summer search selects **11 February 2026** imagery;
the OSM snapshot is from **30 October 2026**. The mapped plant boundary can
include access roads and other non-panel land.

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
    name="Rinconada near Rengo, Chile",
    bbox=(-70.824, -34.412, -70.808, -34.402),
    time_min="2026-01-01",
    time_max="2026-03-01",
    max_cloud_cover=10,
    max_items=5,
    cache_dir=Path(gettempdir()) / "orbitalpv-ground-rengo" if live else bundled,
    cache_prefix="rengo",
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
