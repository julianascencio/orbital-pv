Storage and Space GIS
=====================

OrbitalPV separates scientific history from operational GIS products.

Parquet and DuckDB
------------------

High-volume scientific time series belong in immutable partitioned Parquet
datasets. DuckDB is the local analytical query and rollup engine.

PostgreSQL and PostGIS
----------------------

PostgreSQL stores shared application state and durable job metadata. PostGIS
serves Earth-fixed operational products such as:

* latest satellite positions;
* cached ground-track segments;
* ground stations;
* coverage footprints;
* spatial filtering results.

Scientific orbit vectors remain explicitly labelled with frame and epoch.

Frontend level of detail
------------------------

Browsers should receive downsampled render products rather than raw high-rate
history. Orbit-track caches can be materialized at several sample intervals
for selected-satellite, normal interactive, and fleet-level views.

CesiumJS is the primary 3D orbital visualization engine. A future 2D
operational GIS view can use MapLibre/vector tiles where that is more efficient.
