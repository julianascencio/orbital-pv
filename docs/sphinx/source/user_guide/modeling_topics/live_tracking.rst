Live satellite tracking
=======================

OrbitalPV can display current **predicted** satellite locations on its Cesium
3D globe. The default source is CelesTrak OMM JSON; Skyfield/SGP4 calculates
positions locally. There is no continuous onboard GPS feed and no measured PV
power in this view.

Start the application
---------------------

From a source checkout, run the normal application stack::

    docker compose up --build

Open http://localhost:5173. Select space stations, Starlink, active satellites,
weather satellites or operational GPS; alternatively enter a NORAD catalog ID,
including six- and nine-digit identifiers. Click a marker or select a satellite
in the inspector. The selected ground track spans 45 minutes before and 90
minutes after the calculation time. The globe supports both 3D and 2D modes.
No Cesium Ion token, basemap key or CelesTrak account is required. Natural Earth
imagery and Cesium assets are served locally from the installed Cesium package.

For live-map-only development without PostgreSQL or Redis, start the API from
the repository root::

    uv sync --all-packages --group app --group orbit
    SPACE_PV_BOOTSTRAP_DATABASE=false uv run uvicorn space_pv_api.main:app --port 8000

In another terminal::

    cd apps/space-pv-web
    npm ci
    npm run dev

Use Node 22.18+ or 24. The other database/job endpoints still require their normal
services. In Docker, Vite proxies API traffic to ``http://api:8000``; local
development defaults to ``http://localhost:8000``. Override with
``SPACE_PV_API_PROXY`` when needed.

Current position versus fresh observation
-----------------------------------------

The screen clock and numerical position display update every second. Cesium
interpolates five-second Earth-fixed samples at wall-clock time. The API
recalculates a rolling three-minute window every 60 seconds; this is a local
calculation, not a fresh upstream download. It stops displaying positions beyond
the sample window if refreshes fail. The camera is preserved across refreshes.

The inspector shows source, orbit epoch, element age, download time, calculation
time and the snapshot SHA-256. Element age remains tied to the original orbit
epoch, even when a download just completed. An epoch in the future is identified
as such. Data older than three days or an overdue download cache is flagged;
propagation farther than 14 days from an element epoch is rejected. These are
display policies, not accuracy guarantees. Manoeuvring satellites can be
inaccurate much sooner. Invalid or decayed objects are omitted with an explicit
count. A failed live request never falls back to synthetic tracks.

The **Synthetic demo** tab is deliberately separate, labelled and accelerated
120 times. It is a rendering demonstration, not current tracking.

Coordinates and illumination
-----------------------------

* Latitude and longitude are WGS84 geodetic degrees; altitude is metres above
  the WGS84 ellipsoid, not mean sea level.
* Velocity vectors and speed use the geocentric GCRS inertial frame. They are
  not Earth-relative ground speed.
* Illumination uses the existing finite-Sun, spherical-Earth occultation model
  with Astropy GCRS Sun positions. The screen uses the nearest computed
  five-second illumination sample; eclipse boundaries have that time resolution.
  Penumbra is retained as a fraction. Atmosphere and Earth oblateness are omitted.
* Ground tracks break at the antimeridian. No line is drawn across the world.
* Public GP elements describe orbits, not attitude or available solar-array
  electrical power. PV predictions require additional spacecraft inputs.

Provider policy and persistent caching
--------------------------------------

``SPACE_PV_GP_CACHE_PATH`` defaults to ``data/cache/gp.sqlite3``. A local SQLite
transaction coordinates API workers and stores each source/query's exact JSON
records, retrieval timestamp and checksum. Identical queries, including empty
results, are downloaded at most once per two hours. Browser refreshes, server
restarts and selected-track requests reuse the same snapshot. Selecting a track
from a group reuses that group rather than downloading the object separately.

Do not delete the cache to refresh the map. Mount it persistently. For multiple
hosts, centralize ingestion and distribute snapshots; independent per-host
caches do not enforce a deployment-wide limit. The bounded interactive viewer
shows at most 100 objects, not the entire active/Starlink constellation at once.
The Python connector returns the complete downloaded group for batch work.

CelesTrak requires automated clients to stop on non-200 responses. A redirect,
HTTP error, transport error or malformed JSON pauses this provider in the cache,
including queries for other groups. Existing snapshots can still be returned
with warnings, subject to the separate element-age cutoff. No automated retry
or silent source switching occurs. After a human investigates the problem,
resume ingestion explicitly:

.. code-block:: python

    from orbitalpv.data import GPCache

    GPCache("data/cache/gp.sqlite3").resume("CelesTrak")

This is an operator recovery step, not a browser refresh function. Cache
checksum failures fail closed. The cache is a download/provenance store, not a
replacement for the repository's PostGIS state cache or Parquet scientific
history. This view computes its bounded windows on demand and does not write
per-second states to PostgreSQL.

Python usage
------------

Install the source checkout with the orbit extra::

    python -m pip install '.[orbit]'

Fetch once, then calculate locally:

.. code-block:: python

    from datetime import UTC, datetime, timedelta
    import orbitalpv as opv

    with opv.CelesTrakConnector() as connector:
        snapshot = connector.fetch_gp_cached("data/cache/gp.sqlite3", catnr=25544)
    now = datetime.now(UTC)
    states = opv.propagate_ground_track(
        snapshot.records[0], [now + timedelta(seconds=i) for i in range(60)]
    )
    print(states[0])
    print(snapshot.retrieved_at, snapshot.sha256, snapshot.warning)

The same propagation helper accepts compatible OMM JSON from Space-Track:

.. code-block:: python

    import os
    from orbitalpv.environment_data import SpaceTrackConnector

    with SpaceTrackConnector() as connector:
        connector.login(os.environ["SPACETRACK_IDENTITY"], os.environ["SPACETRACK_PASSWORD"])
        snapshot = connector.latest_gp_cached(25544, cache_path="data/cache/gp.sqlite3")

Current Space-Track snapshots use a conservative two-hour cache too. Historical
work should use the existing ``gp_history`` connector with its mandatory disk
cache, and elements near the historical time of interest. Account credentials
are required; they are never browser configuration.

An optional direct-position API is available through N2YO:

.. code-block:: python

    # Set N2YO_API_KEY on the server first.
    import orbitalpv as opv

    with opv.N2YOConnector() as connector:
        result = connector.positions(
            25544, observer_lat=28.4, observer_lon=-16.3,
            observer_alt_m=500, seconds=60,
        )
    print(result["positions"])

N2YO's ``sataltitude`` is kilometres while observer altitude is metres. Its
position endpoint does not supply an element epoch; OrbitalPV keeps this
unknown instead of substituting the retrieval time. Positions remain provider
predictions. The free quota is 1,000 position calls/hour with at most 300 seconds
per call. The optional connector makes one call per invocation and no retries;
applications must manage their own call budget. N2YO and Space-Track are Python
alternatives, not automatic fallbacks or frontend provider switches. The default
live web view is CelesTrak only.

API contracts
-------------

``GET /api/v1/map/live?group=stations&limit=100``
    Current bounded scene with provenance, warnings and sample timestamps.

``GET /api/v1/map/live?norad_id=25544``
    A single satellite from the individually cached catalog query.

``GET /api/v1/map/live/25544/track?group=stations``
    Selected ground track using the existing group snapshot.

``GET /api/v1/map/live/25544/track?individual=true``
    Selected ground track using an individual catalog query.

Input validation returns 422; unavailable provider data returns 503. A satellite
missing from the selected group returns 404. Existing ``/map/demo`` and PostGIS
map endpoints remain available.

Validation and sources
----------------------

The offline gallery example uses a pinned May 2024 ISS OMM from the official
Skyfield guide. It deliberately propagates near that epoch, never at today's
date. Tests compare WGS84 coordinates with an independent python-sgp4 + Astropy
TEME-to-ITRS transformation and exercise cache reuse, concurrent downloads,
provider pauses, expiry, six-digit IDs, credential redaction and antimeridian
handling. This validates software contracts, not flight tracking accuracy.

* `CelesTrak GP formats <https://celestrak.org/NORAD/documentation/gp-data-formats.php>`_
* `CelesTrak usage policy <https://celestrak.org/usage-policy.php>`_
* `Skyfield Earth satellites <https://rhodesmill.org/skyfield/earth-satellites.html>`_
* `Space-Track API documentation <https://www.space-track.org/documentation>`_
* `N2YO REST API <https://www.n2yo.com/api/>`_
* `Cesium sampled positions <https://cesium.com/learn/cesiumjs/ref-doc/SampledPositionProperty.html>`_
