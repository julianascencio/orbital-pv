Ground-input snapshots
======================

These are small REAL source-data snapshots for an offline gallery build,
not synthetic images, model predictions or a reproduction of a paper.

Cestas, France
--------------

Area: WGS84 (west, south, east, north) =
(-0.833, 44.709, -0.795, 44.742), Cestas solar park, France.

Sentinel-2
~~~~~~~~~~

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
~~~~~~~~~~~~~

© OpenStreetMap contributors. Open Database License (ODbL-1.0):
https://www.openstreetmap.org/copyright
https://opendatacommons.org/licenses/odbl/1-0/

cestas-osm.json is an unmodified public Overpass response retrieved on
2026-10-30. It contains 23 solar-tagged ways, including the enclosing plant
and mapped panel groups. The source timestamp is in osm3s.timestamp_osm_base.
The API query and byte-level SHA-256 are in cestas-osm.json.meta.json.
This is not a count of 23 power plants, an exhaustive inventory, or a
contemporaneous label set for the 2024 satellite acquisition.

Rinconada near Rengo, Chile
--------------------------

Area: WGS84 (west, south, east, north) =
(-70.824, -34.412, -70.808, -34.402).

Site identity
~~~~~~~~~~~~~

PMGD Parque Fotovoltaico Rinconada is a photovoltaic plant in the Rengo
commune, O'Higgins region. Chile's environmental regulator identifies
PFV RINCONADA and GR TAMARUGO SPA in its registry:
https://snifa.sma.gob.cl/UnidadFiscalizable/Ficha/16386

The EPC's project sheet records commissioning in 2019 and nominal capacity
of 8 MW. These are source records, not measurements from these images:
https://grupojrortiz.com/wp-content/uploads/2023/08/Planta-fotovoltaica-Rinconada.pdf

The mapped plant is OSM way 829933528:
https://www.openstreetmap.org/way/829933528
The requested bbox contains all vertices of its source outline, whose bounds
are (-70.8219759, -34.4099005, -70.8105282, -34.4041911).
Rinconada is distinct from the other projects called Rengo Solar or Santa
Isabel/Santa Elizabeth in the surrounding area.

Sentinel-2
~~~~~~~~~~

Contains modified Copernicus Sentinel data (2026), processed by Element 84.
Scene: S2C_T19HCC_20260211T144012_L2A
Acquired: 2026-02-11T14:52:20.673000Z
Collection: sentinel-2-c1-l2a
API: https://earth-search.aws.element84.com/v1
Scene-wide cloud cover: 0.001257 percent, not a local cloud-mask result.
The collection and Sentinel data legal-notice links above also apply here.

rengo-scenes.json is a bounded search snapshot for 2026-01-01 through
2026-03-01, a Southern Hemisphere summer window, with cloud cover <= 10
percent and max_items=5. The API reported 22 matches; the snapshot retains
the first 5 sorted by increasing cloud cover, with limit_reached=true.
It is not a complete inventory of matching acquisitions. The example selects
the first returned item and preserves all metadata for the returned scenes.

The GeoTIFFs contain native pixel-aligned crops, without reprojection,
resampling, cloud masking or applied reflectance scaling:

* rengo-visual.tif: uint8 display-ready RGB, 10 m, 3 x 114 x 150.
* rengo-red.tif: uint16 raw B04 digital numbers, 10 m, 1 x 114 x 150.
* rengo-scl.tif: uint8 scene-classification codes, 20 m, 1 x 58 x 75.

The crop CRS is EPSG:32719 (UTM zone 19 south). The red band's explicit
source scale is 0.0001 and offset is -0.1, retained as GeoTIFF metadata.
The red reflectance range after explicit calibration is 0.0083 to 0.4893.
The SCL crop contains vegetation (4), not vegetated (5), and unclassified (7)
codes. These are quality classes, not photovoltaic-panel labels.

RGB/red bounds: (332340, 6190650, 333840, 6191790) metres.
SCL bounds: (332340, 6190640, 333840, 6191800) metres.
The grids are aligned outwards independently at their native resolution;
the SCL north/south extent is therefore slightly different. Red and SCL have
no nodata samples; the RGB source's zero-nodata convention masks four band
samples. The example preserves masks and fills RGB nodata with zero only for
display. A 10 m image cannot resolve individual modules.

OpenStreetMap
~~~~~~~~~~~~~

© OpenStreetMap contributors, ODbL-1.0; the license links above also apply.
rengo-osm.json is the unmodified bounded Overpass response retrieved on
2026-10-30, with source timestamp 2026-10-30T09:53:40Z. It contains exactly
one way, 829933528, with plant:method=photovoltaic, plant:source=solar,
power=plant, name=PMGD Parque Fotovoltaico Rinconada, operator=GR Tamarugo,
and plant:output:electricity=8 MW. All original tags and geometry are kept.

This is the plant boundary, which can include roads and non-panel land.
No separately mapped panel-group features were returned. The October 2026
OSM snapshot is not a contemporaneous label set for the February 2026 image.

Each rengo-* source file has a SHA-256 sidecar with query or crop metadata,
source URL and retrieval time. Raster sidecars include the full STAC item,
native grid, acquisition date and unmodified calibration metadata. Only
sidecar path fields were relocated to repository-relative paths; source
JSON payloads and crop pixels were not altered.

Paper
-----

Dunnett, S., Sorichetta, A., Taylor, G. and Eigenbrod, F. (2020).
Harmonised global datasets of wind and solar farm locations and power.
Scientific Data 7, 130. https://doi.org/10.1038/s41597-020-0469-8

The paper derives farm inputs from OSM, not image segmentation. Imagery here
provides inspection context. GHSL filtering, topology reconstruction,
clustering, capacity calibration and historical validation are separate work.

The repository's MIT software license does not replace these data licenses.
