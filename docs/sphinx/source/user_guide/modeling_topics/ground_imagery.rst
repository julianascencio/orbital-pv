Ground satellite imagery and renewable-energy features
======================================================

Retrieve Sentinel-2 images for a geographic area through Python, then retain
the acquisition metadata alongside the pixels. The ground connector uses
Element 84's public Earth Search STAC API and Sentinel-2 Collection 1 Level-2A
COGs. Public HTTPS assets need no API key or AWS account. [#earthsearch]_

This supports inspection of terrestrial PV sites and preparation of inputs
for later mapping methods. It complements OrbitalPV's spacecraft telemetry
and orbit connectors.

Relationship to the requested paper
-----------------------------------

Dunnett et al. (2020), *Harmonised global datasets of wind and solar farm
locations and power*, starts with OpenStreetMap features retrieved through
Overpass. It selects ``generator:source`` or ``plant:source`` tags with values
``solar`` and ``wind``. The workflow also uses 2015 GHSL settlement classes
to flag urban areas and water, spatial grouping of features, and independent
capacity records to calibrate estimates. [#dunnett]_

The connectors here retrieve imagery and the raw OSM input features. Satellite
imagery is an extension for visual inspection or a future mapping method;
the paper does not infer its global inventory from satellite pixels.
The additional :doc:`pv_footprints` methods implement image classification,
GHSL retrieval, polygon deduplication, farm grouping and capacity calibration.
They distinguish inferred footprints from source OSM features and report
validation separately. A current OSM query is a different snapshot from the
study's original extract; the examples do not recreate its complete inventory.

The original data and scripts are available in the authors' versioned
Figshare archive, DOI ``10.6084/m9.figshare.11310269.v2``. Its GeoPackage files
retain geometries; centroid-only tables are insufficient for recovering
panel outlines. [#archive]_

Install the new API
-------------------

This connector is unreleased. Install the repository revision containing it,
including the optional raster reader and plotting packages:

.. code-block:: bash

   python -m pip install "orbital-pv[ground,examples] @ git+https://github.com/julianascencio/orbital-pv.git"

For a reproducible analysis, pin the Git commit and keep the returned STAC
metadata, OSM response, query parameters, and output imagery together.

Map a PV site with shared utilities
-------------------------------------

``load_pv_site`` combines the scene search, native image crops, verified local
cache and OSM query. The same plotting functions work for Cestas, Rinconada
and Icor in Tenerife; only the site name, bounding box and dates change.

.. code-block:: python

   import matplotlib.pyplot as plt
   import orbitalpv as opv

   site = opv.load_pv_site(
       name="Icor PV site, Arico, Tenerife",
       bbox=(-16.447, 28.192, -16.439, 28.198),
       time_min="2026-06-01", time_max="2026-09-01",
       max_cloud_cover=10, max_items=5,
       cache_dir="data/icor", cache_prefix="tenerife",
   )
   opv.plot_pv_site(site, overlay_osm=True)
   opv.plot_pv_site_quality(site)
   plt.show()

The returned ``PVSite`` keeps the bounded search in ``site.scenes``, the
selected STAC item in ``site.item``, the original Overpass response in
``site.osm`` and each native ``GroundImage`` in ``site.images``. Call
``site.summary()`` for acquisition, search-limit, grid and source-feature
metadata. For direct spectral work, use
``site.images["red"].reflectance()``; its raw pixels remain unchanged.

.. list-table:: Reusable PV mapping utilities
   :header-rows: 1
   :widths: 32 68

   * - Utility
     - Purpose
   * - ``load_pv_site``
     - Load or retrieve one site's imagery and original mapped solar features.
   * - ``load_ground_image``
     - Restore a saved crop with its checksum, native grid, mask and source metadata.
   * - ``plot_pv_site``
     - Display RGB and optionally project OSM features into the image's CRS.
   * - ``plot_pv_site_quality``
     - Display calibrated red reflectance beside categorical SCL on its native grid.

The default assets are ``visual``, ``red`` and ``scl``. Search still selects
the first returned scene by scene-wide cloud cover unless ``scene_id`` is
specified; an explicit scene must occur in the bounded search results.
Inspect local quality classes and the image before relying on that choice.
Different native grids are retained. Plotting functions return Matplotlib
axes or a figure/axes pair for customization and leave ``plt.show()`` to
the caller.

The cache uses ``<prefix>-scenes.json``, ``<prefix>-osm.json`` and
``<prefix>-<asset>.tif`` with their provenance sidecars. An existing cache
must match its request, selected scene, area, asset and checksum. Choose a
new directory/prefix when changing a study, or pass ``refresh=True`` to
retrieve fresh inputs explicitly. ``offline=True`` requires a complete,
valid local cache and prevents network access; it cannot be combined with
``refresh=True``. The gallery uses this mode for its bundled snapshots.

The overlays retain their OpenStreetMap provenance. Plant boundaries and
panel-group outlines can overlap, so their areas must not be summed as if
they were distinct sites. Geometry members and gaps stay separate, and
image and map dates are shown independently.

Search and read a small image
-----------------------------

This example searches near Cestas, France. Bounding boxes use WGS84 longitude
and latitude in the order ``(west, south, east, north)``. Search results are a
STAC ``FeatureCollection`` dictionary. Its ``features`` list contains items,
and each item's ``assets`` dictionary describes the available files.
Time bounds are inclusive and interpreted in UTC; a date without a time
means midnight. For example, ``time_max="2024-09-01"`` includes midnight
at the start of 1 September, not the whole day.

.. code-block:: python

   from pathlib import Path

   import orbitalpv as opv

   output = Path("data")
   output.mkdir(exist_ok=True)
   bbox = (-0.833, 44.709, -0.795, 44.742)
   with opv.Sentinel2GroundConnector() as connector:
       scenes = connector.search(
           bbox=bbox,
           time_min="2024-06-01",
           time_max="2024-09-01",
           max_cloud_cover=10,
           max_items=10,
           cache_path=output / "cestas-scenes.json",
       )
       if not scenes["features"]:
           raise RuntimeError("No scenes; broaden the dates or cloud limit.")

       item = scenes["features"][0]
       print(item["id"], item["properties"]["datetime"])
       print(item["properties"].get("eo:cloud_cover"))
       print(sorted(item["assets"]))
       print("Result cap reached:", scenes["context"]["limit_reached"])
       rgb = connector.read_image(item, bbox=bbox, asset="visual")
       rgb.save_geotiff(output / "cestas-rgb.tif")

``max_items`` caps the returned scenes; a bounded search is not a complete
inventory of every matching acquisition. Inspect
``scenes["context"]["limit_reached"]`` when completeness matters. Search uses
spatial intersection, but ``read_image`` requires the entire requested bbox
to fit within the scene's native raster bounds. It raises an error for
partial coverage instead of silently returning a smaller area. Pixels within
the raster can still be nodata; inspect the returned mask.

``read_image`` reads an area from a Cloud-Optimized GeoTIFF instead of
downloading the full scene. ``GroundImage.data`` is a masked array ordered
``(band, row, column)``. ``crs`` identifies its coordinate system,
``transform`` contains six affine coefficients, and ``bounds`` are expressed
in that projected coordinate system. These bounds are not the input
longitude/latitude bbox. ``save_geotiff`` writes raw values with georeferencing
and provenance. ``read_image`` also enforces ``max_pixels`` as a limit on
the total number of band samples: bands multiplied by rows and columns.
A three-band RGB crop therefore uses three samples per spatial pixel.

For an intentional full-file download, use:

.. code-block:: python

   with opv.Sentinel2GroundConnector() as connector:
       connector.download_asset(item, "visual", output / "full-scene.tif")

Full scenes are substantially larger than site crops; inspect the asset's
size metadata first.

Choose the right pixels
-----------------------

.. list-table:: Common Sentinel-2 Collection 1 assets
   :header-rows: 1
   :widths: 23 17 60

   * - Asset key
     - Pixel size
     - Meaning
   * - ``visual``
     - 10 m
     - Display-ready three-band RGB; not quantitative reflectance.
   * - ``red``, ``green``, ``blue``, ``nir``
     - 10 m
     - Spectral bands stored as digital numbers with calibration metadata.
   * - ``swir16``, ``swir22``
     - 20 m
     - Shortwave infrared bands; a different native grid from RGB.
   * - ``scl``
     - 20 m
     - Categorical scene classification, including cloud and shadow classes.

Sentinel-2 Level-2A includes surface reflectance and scene classification
products. [#sentinel]_ A 10 m pixel is useful for large-site context but does
not provide individual panel boundaries. Enlarging a display or resampling
to a finer grid does not add spatial information.

``eo:cloud_cover`` describes the scene, not cloudiness at the selected farm.
Use ``scl`` to inspect local cloud, shadow and snow classes. Align it to the
image grid before applying a pixel mask; use nearest-neighbour resampling
for categorical classes. A low scene-wide cloud percentage cannot guarantee
a clear site.

Spectral crops preserve the original digital numbers. Conversion is explicit:

.. code-block:: python

   with opv.Sentinel2GroundConnector() as connector:
       red = connector.read_image(item, bbox=bbox, asset="red")
   surface_reflectance = red.reflectance()
   red.save_geotiff(output / "cestas-red-raw.tif")

``reflectance()`` uses the spectral asset's scale and offset, preserving its
missing-data mask. Retain the distinction between the converted array and
the raw GeoTIFF saved above. Do not apply reflectance conversion to the
display-ready RGB product or categorical SCL values.

The default collection is ``sentinel-2-c1-l2a``. Earth Search documents
collection-specific processing, including offsets; its legacy
``sentinel-2-l2a`` collection has reported calibration-metadata inconsistencies.
Mixing the collections or applying a fixed offset to every source is not a
safe substitute for inspecting metadata. [#collections]_ [#offsets]_

Retrieve the paper's OSM feature inputs
---------------------------------------

.. code-block:: python

   with opv.OpenStreetMapEnergyConnector() as connector:
       osm = connector.fetch_energy_features(
           bbox=bbox,
           sources=("solar",),
           cache_path=output / "cestas-osm.json",
       )
   print(len(osm["elements"]))
   print(osm.get("osm3s", {}))

The result retains the Overpass response, including raw ``elements``, tags,
relation members, geometry and available snapshot timestamps. It is input
data, not a normalized inventory of unique power plants. Multiple OSM
features can represent panels and the enclosing plant. Missing features
can reflect incomplete mapping.

The query selects ``generator:source``, ``plant:source``, and legacy
``power_source`` tags. Including the legacy key extends the paper's stated
selection. A ``solar`` source tag alone does not establish photovoltaic
technology; inspect method tags such as ``generator:method=photovoltaic``
and retain uncertain cases for review rather than treating every solar
feature as PV.

Relations can describe multipolygons with holes or multiple outer rings.
Automatic polygon assembly needs explicit topology handling; treating a
relation's member coordinates as one closed ring can produce an incorrect
footprint. This connector preserves the source structure for subsequent
processing. OSM queries are capped at one square degree of bbox area
(``(east - west) * (north - south)``), a geographic limit rather than a
fixed area in square kilometres. Large studies should use appropriately
bounded queries or bulk OSM extracts instead of treating a public Overpass
instance as an unlimited global download service. [#overpass]_

The executable image-and-feature walkthroughs cover
:doc:`Cestas, France <../../gallery/ground_imagery/plot_ground_satellite_inputs>`,
:doc:`Rinconada near Rengo, Chile <../../gallery/ground_imagery/plot_rengo_solar_plant>`
and :doc:`Icor in Tenerife <../../gallery/ground_imagery/plot_tenerife_solar_plant>`.

Attribution and primary sources
-------------------------------

For imagery, retain acquisition identifiers, source assets and the
Copernicus Sentinel attribution; distinguish modifications when publishing
processed images. Follow the Sentinel data legal notice linked by the
collection. OSM data require attribution to OpenStreetMap contributors and
are available under the Open Database License; derived database
redistribution should follow those terms. [#osmlicense]_ The repository's
software license does not replace the input-data licenses.

.. [#dunnett] Dunnett, S., Sorichetta, A., Taylor, G. and Eigenbrod, F. (2020).
   `Harmonised global datasets of wind and solar farm locations and power
   <https://doi.org/10.1038/s41597-020-0469-8>`_. Scientific Data 7, 130.

.. [#archive] Dunnett, S. (2020). `Original data and scripts, version 2
   <https://doi.org/10.6084/m9.figshare.11310269.v2>`_. Figshare.

.. [#earthsearch] Element 84. `Earth Search STAC API
   <https://github.com/Element84/earth-search>`_ and
   `live Collection 1 metadata, including legal-notice link
   <https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a>`_.

.. [#collections] Element 84. `Sentinel-2 collection and calibration notes
   <https://github.com/Element84/earth-search/blob/main/docs/collections/sentinel-2-l2a.md>`_.

.. [#sentinel] Copernicus. `Sentinel-2 products and radiometric conventions
   <https://sentiwiki.copernicus.eu/web/s2-products>`_.

.. [#offsets] Element 84 issue tracker. `Legacy Sentinel-2 L2A offset anomalies
   <https://github.com/Element84/earth-search/issues/71>`_.

.. [#overpass] OpenStreetMap. `Overpass API documentation
   <https://wiki.openstreetmap.org/wiki/Overpass_API>`_.

.. [#osmlicense] OpenStreetMap. `Copyright, attribution and Open Database License
   <https://www.openstreetmap.org/copyright>`_.
