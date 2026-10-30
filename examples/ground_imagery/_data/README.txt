Ground-input snapshots
======================

These are small REAL source-data snapshots for an offline gallery build,
not synthetic images, model predictions or a reproduction of a paper.

Additional inputs for footprint detection and inventories
---------------------------------------------------------

The image-classification example adds blue (B02), green (B03), near-infrared
(B08), SWIR16 (B11), and SWIR22 (B12) to each site's existing red (B04) band.
All are crops of exactly the same STAC scene recorded in the site sections
below. Blue, green and NIR retain native 10 m pixels; SWIR retains native
20 m pixels. Each crop has its own complete STAC provenance, raw calibration
metadata and SHA-256 sidecar. No calibration, cloud masking or resampling
has been applied to the saved source pixels. The model feature builder
performs these operations explicitly and records them separately.

The source snapshots support an image-only classifier trained on Cestas's
generator polygons and tested against Tenerife's separate, later OSM labels.
OSM polygons are weak reference labels, not surveyed contemporaneous truth.
Outside-map negatives are an explicit assumption, and a 20 m buffer outside
positive polygons is unknown. The unchanged detector also predicts Rinconada,
but that site's plant perimeter does not supply panel-level validation.

GHSL historical settlement context
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* cestas-ghsl.tif: 5 x 4 native 1 km cells.
* rengo-ghsl.tif: 2 x 3 native 1 km cells.
* tenerife-ghsl.tif: 2 x 2 native 1 km cells.

These are unresampled World Mollweide (ESRI:54009) crops of GHS-SMOD epoch
2015, release R2023A, version 2.0. They are NOT the R2019A edition used by
Dunnett et al. (2020). The later release is recorded explicitly; no substitute
is silently presented as the original paper input. Codes are water 10,
rural 11/12/13, and urban 21/22/23/30. Unknown and masked cells remain unknown.
These classes provide historical settlement context, not current PV land use.

Official product:
https://human-settlement.emergency.copernicus.eu/ghs_smod2023.php
Source archive:
https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E2015_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E2015_GLOBE_R2023A_54009_1000_V2_0.zip
Archive bytes: 29,185,689
Archive SHA-256:
cd5bc9ef9521bdd5600520005c5a769afc11ba74384f05fd96c0739db5c7f30e

GHSL source data copyright European Union. Reuse is allowed with source
acknowledgement; this repository does not imply European Commission endorsement.
https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_POP_GLOBE_R2019A/copyright.txt
The individual sidecars record product identity, exact source, native grid,
query and crop checksum. The global source archive is not bundled.

Independent capacity calibration table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

wiki_solar_join.csv is the unchanged anonymised table from:
global_wind_solar_2020/analysis/data/wiki_solar_join.csv
within the authors' original version 2 archive:
https://doi.org/10.6084/m9.figshare.11310269.v2
https://ndownloader.figshare.com/files/21979983

The archive metadata declares CC0:
https://creativecommons.org/publicdomain/zero/1.0/
Credit: Sebastian Dunnett (2020), Harmonised global datasets of wind and
solar farm locations and power. The associated paper is:
https://doi.org/10.1038/s41597-020-0469-8

The table contains 1,392 unique sol_id records across 49 countries. Its power
field is reported MW without a declared AC/DC basis; panel.area is an OSM
polygon-area proxy in km2, not surveyed module area. All 159 Spanish records
are withheld from fitting. The historical capacity >= 1000 MW cutoff excludes
one non-Spanish training record. Of the Spanish records, 158 are inside the
calibration predictor range and one is withheld rather than extrapolated.
This table is one component of the paper's pooled calibration data, not the
complete original pooled model or its full published inventory.

Bytes: 107,844
SHA-256: 35015b31f01d8342d2305c5ef28cb280249e9a8f21e4335912fbe8da6f1bcd21
The .meta.json preserves the archive/version, full member path and checksum.

pv-sites.json records the three retrieval configurations for the analysis.
Model predictions and derived inventories are written separately under the
caller-selected output directory; no predictions are presented as source data.

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

Icor in Arico, Tenerife
----------------------

Area: WGS84 (west, south, east, north) =
(-16.447, 28.192, -16.439, 28.198).

Site identity
~~~~~~~~~~~~~

The Instituto Tecnologico y de Energias Renovables (ITER) infrastructure
inventory identifies Icor as a 2000 kW photovoltaic installation (record 6),
at longitude -16.442229, latitude 28.194341:
https://datos.gob.es/es/catalogo/la0012321-infraestructuras-de-generacion-de-energia-en-tenerife
https://datos.tenerife.es/ckan/dataset/fa991fa9-a113-452c-9f1b-331b1ffefbe1/resource/2782375b-f2c7-4a05-a685-4eee554a6b1b/download/plantas-fotovoltaicas-y-parques-eolicos.geojson

ITER's 2019 operating programme, printed page 26 (PDF page index 25), also
records Icor as an existing 2 MW ground-mounted plant in Arico:
https://www.iter.es/wp-content/uploads/2019/05/PAIF-ITER-2019-_compressed-1.pdf
Capacity is from these source records; it is not inferred from the pixels or
the OSM tags. The example uses the existing Icor site, distinct from Icor II.

The official location point lies within OSM plant way 430266023. Way 430266024
encloses the adjacent array block. Both have photovoltaic method tags:
https://www.openstreetmap.org/way/430266023
https://www.openstreetmap.org/way/430266024
Their combined source bounds are
(-16.4450687, 28.193818, -16.441437, 28.1968758), inside the example bbox.

Sentinel-2
~~~~~~~~~~

Contains modified Copernicus Sentinel data (2026), processed by Element 84.
Scene: S2A_T28RCS_20260804T115232_L2A
Acquired: 2026-08-04T11:53:59.065000Z
Collection: sentinel-2-c1-l2a
API: https://earth-search.aws.element84.com/v1
Scene-wide cloud cover: 0.155066 percent, not a local cloud-mask result.
The collection and Sentinel data legal-notice links above also apply here.

tenerife-scenes.json is a bounded search snapshot for 2026-06-01 through
2026-09-01, cloud cover <= 10 percent and max_items=5. The API reported nine
matches; the snapshot retains the first five sorted by increasing cloud
cover, with limit_reached=true. The example selects the first returned item.

The GeoTIFFs contain native pixel-aligned crops, without reprojection,
resampling, cloud masking or applied reflectance scaling:

* tenerife-visual.tif: uint8 display-ready RGB, 10 m, 3 x 69 x 80.
* tenerife-red.tif: uint16 raw B04 digital numbers, 10 m, 1 x 69 x 80.
* tenerife-scl.tif: uint8 scene-classification codes, 20 m, 1 x 35 x 41.

The crop CRS is EPSG:32628 (UTM zone 28 north). The red band's explicit source
scale is 0.0001 and offset is -0.1, retained as GeoTIFF metadata. Explicitly
calibrated red reflectance ranges from 0.0807 to 0.3743. The SCL crop contains
one vegetation (4) pixel and 1434 not-vegetated (5) pixels. These categories
do not identify photovoltaic modules. There are no nodata samples in any crop.

RGB/red bounds: (357970, 3119300, 358770, 3119990) metres.
SCL bounds: (357960, 3119300, 358780, 3120000) metres.
Each grid retains its own outward pixel alignment. Native 10 m imagery gives
site context; the OSM vectors can contain finer detail than these pixels.

OpenStreetMap
~~~~~~~~~~~~~

© OpenStreetMap contributors, ODbL-1.0; the license links above also apply.
tenerife-osm.json is the unmodified bounded Overpass response, with source
timestamp 2026-10-30T10:23:04Z. It contains 52 ways: two power=plant boundaries
and 50 power=generator PV row/group outlines. These are mapped objects,
not 52 unique plants. Their geometries overlap and their areas must not be
summed. Capacity tags contain only "yes"; the 2 MW value comes from ITER.
The October map snapshot is not contemporaneous with the August image.

All five tenerife-* payloads have checksum and provenance sidecars. The
source queries, full STAC items, native grids and original calibration are
retained. Only the sidecar path fields were relocated to repository-relative
paths; the source JSON payloads and crop pixels were not altered.

Paper
-----

Dunnett, S., Sorichetta, A., Taylor, G. and Eigenbrod, F. (2020).
Harmonised global datasets of wind and solar farm locations and power.
Scientific Data 7, 130. https://doi.org/10.1038/s41597-020-0469-8

The paper derives farm inputs from OSM, not image segmentation. Imagery here
provides inspection context. GHSL filtering, topology reconstruction,
clustering, capacity calibration and historical validation are separate work.

The repository's MIT software license does not replace these data licenses.
