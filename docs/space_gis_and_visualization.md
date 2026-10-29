# Space GIS and spatiotemporal visualization

Space PV Analytics has two different kinds of spatial data and must not mix them.

## 1. Scientific reference-frame state

Orbit propagation produces time-dependent vectors in frames such as TEME, GCRS/ECI,
ITRS/ECEF and mission-specific SPICE frames. These are scientific states. Store the
frame, epoch, units and numerical vector explicitly. Do **not** label an inertial vector
as a PostGIS longitude/latitude geometry.

Authoritative/high-rate states belong in Parquet and are queried with DuckDB.

Suggested partitioning:

```text
data/lake/
  bronze/telemetry/source=<source>/satellite_id=<id>/date=YYYY-MM-DD/*.parquet
  silver/orbit/satellite_id=<id>/date=YYYY-MM-DD/*.parquet
  silver/pv/satellite_id=<id>/date=YYYY-MM-DD/*.parquet
  gold/performance/satellite_id=<id>/date=YYYY-MM-DD/*.parquet
```

Within orbit Parquet use columns such as:

```text
timestamp, frame, x_m, y_m, z_m, vx_m_s, vy_m_s, vz_m_s,
longitude_deg, latitude_deg, altitude_m, illumination_fraction
```

## 2. Earth GIS/render products

PostGIS is the hot serving layer for Earth-fixed products:

- latest satellite position
- short cached orbit/ground-track segments
- ground stations
- sensor/communication footprints
- areas of interest
- map selection/intersection queries

The `gis.satellite_latest_state` table is intentionally one row per tracked satellite.
The frontend can refresh thousands of satellites without scanning historical orbit data.

`gis.orbit_track_segments` is a **render cache**, not the scientific archive. A segment
stores compact time-aware samples plus a PostGIS LineString for spatial filtering.
Use multiple LODs, for example:

| LOD | Interval | Typical use |
| --- | ---: | --- |
| 0 | 2–5 s | selected satellite, close zoom |
| 1 | 15–30 s | normal interactive orbit |
| 2 | 60–120 s | many satellites / global overview |

Expire or regenerate these segments. Do not permanently store every propagated second
for every catalog object in PostgreSQL.

## 3. Fast frontend time series

The raw telemetry table is normalized/tall for connector flexibility. It is not the
format a browser should consume for a 90-day chart.

DuckDB therefore has `telemetry_rollups` with min/max/avg/last/count buckets. The API
should select a bucket size based on viewport width/time range so a chart normally
receives roughly 500–2,000 points rather than millions.

A later production deployment should have Celery workers write immutable partitioned
Parquet files. DuckDB is embedded and is best used as a query engine over the lake,
not as a shared multi-process transactional database.

## 4. Frontend engines

### CesiumJS — primary space view

Use for:

- 3D globe
- altitude-aware satellites
- time animation
- sampled orbital positions
- ground tracks
- footprints/cones
- Earth/Sun visualization later
- attitude and satellite models later

Cesium `SampledPositionProperty` maps naturally onto orbit samples `[time, lon, lat,
altitude]`.

### MapLibre — secondary 2D operational GIS view

Use later for:

- dense ground station maps
- AOIs
- 2D ground tracks
- vector tiles
- heat maps
- operational dashboards where a 3D globe is unnecessary

### deck.gl — optional GPU layer system

Useful later when rendering very large point/arc/vector datasets, especially on top of
a 2D/3D map. It should not replace Cesium as the canonical orbital/time engine.

## 5. API serving strategy

Do not expose database tables directly.

```text
GET /api/v1/map/satellites/latest
GET /api/v1/map/satellites/{id}/track?start=...&end=...&lod=1
GET /api/v1/map/demo
```

For many static GIS features add vector tiles later (`MVT`) rather than enormous GeoJSON.
PostGIS and DuckDB Spatial both provide geometry functions suitable for tile pipelines.

For orbit animation, compact sampled-position JSON or CZML is preferable to MVT because
time belongs to each position sample.

## 6. Scaling rules

1. Postgres/PostGIS = catalog + operational state + hot render cache.
2. Parquet = immutable high-volume scientific history.
3. DuckDB = analytical query/rollup engine over Parquet/local labs.
4. Redis = transient queue/cache only, never source of truth.
5. Browser receives LOD/downsampled products, not raw high-rate telemetry.
6. Precompute the expensive transformation chain: inertial state -> Earth-fixed ->
   lon/lat/alt -> ground track/footprint.
7. Cache by satellite, time window, model/ephemeris version and LOD.

## 7. Antimeridian handling

Ground tracks routinely cross +180/-180 longitude. A naïve WGS84 LineString draws a
false line across the world and gives poor bounding boxes. Render-cache ground tracks
are therefore stored as `MULTILINESTRING` and split when wrapped longitude jumps across
the antimeridian. Cesium's 3D time-sampled path remains based on the actual position
samples and does not depend on this 2D split.
