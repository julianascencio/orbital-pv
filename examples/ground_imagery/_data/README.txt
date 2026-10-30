Cestas ground-input snapshots
=============================

These are small REAL source-data snapshots for an offline gallery build,
not synthetic images, model predictions or a reproduction of a paper.

Area: WGS84 (west, south, east, north) =
(-0.833, 44.709, -0.795, 44.742), Cestas solar park, France.

Sentinel-2
---------

Contains modified Copernicus Sentinel data (2024), processed by Element 84.
Scene: S2A_T30TXQ_20240810T105747_L2A
Acquired: 2024-08-10T11:08:48.933000Z
Collection: sentinel-2-c1-l2a
API: https://earth-search.aws.element84.com/v1
Collection metadata and data legal notice:
https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a
https://dataspace.copernicus.eu/terms-and-conditions

The GeoTIFFs contain native pixel-aligned crops, without reprojection,
resampling, cloud masking or applied reflectance scaling:

* cestas-visual.tif: uint8 display-ready RGB, 10 m, 3 x 376 x 312.
* cestas-red.tif: uint16 raw B04 digital numbers, 10 m, 1 x 376 x 312.
* cestas-scl.tif: uint8 scene-classification codes, 20 m, 1 x 188 x 157.

The crop CRS is EPSG:32630. The red band's explicit source scale is 0.0001
and offset is -0.1; these are stored as GeoTIFF metadata, not applied to the
pixels. Mask nodata before conversion. Visual RGB is not reflectance.

Each .meta.json stores the full source STAC item, asset URL, acquisition
information, requested/actual bounds, native transform, retrieval time and
SHA-256 of its associated file. Paths were relocated into this example folder
without altering the source JSON payloads or crop pixels. cestas-scenes.json
is a bounded STAC search snapshot with 3 matching scenes, not a global catalog.

OpenStreetMap
-------------

© OpenStreetMap contributors. Open Database License (ODbL-1.0):
https://www.openstreetmap.org/copyright
https://opendatacommons.org/licenses/odbl/1-0/

cestas-osm.json is an unmodified public Overpass response retrieved on
2026-10-30. It contains 23 solar-tagged ways, including the enclosing plant
and mapped panel groups. The source timestamp is in osm3s.timestamp_osm_base.
The API query and byte-level SHA-256 are in cestas-osm.json.meta.json.
This is not a count of 23 power plants, an exhaustive inventory, or a
contemporaneous label set for the 2024 satellite acquisition.

Paper
-----

Dunnett, S., Sorichetta, A., Taylor, G. and Eigenbrod, F. (2020).
Harmonised global datasets of wind and solar farm locations and power.
Scientific Data 7, 130. https://doi.org/10.1038/s41597-020-0469-8

The paper derives farm inputs from OSM, not image segmentation. Imagery here
provides inspection context. GHSL filtering, topology reconstruction,
clustering, capacity calibration and historical validation are separate work.

The repository's MIT software license does not replace these data licenses.
