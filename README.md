# OrbitalPV

Open-source full-stack lab for **spacecraft photovoltaic performance analytics**: PV physics, orbit/Sun geometry, real spacecraft data connectors, degradation/anomaly analytics, reproducible research labs, and a web application platform.

The structure follows the same separation-of-concerns philosophy as Bazefield analytics: domain models, physics engines, connectors and analytics are independent workspace packages with a single `uv` environment and consistent quality tooling.

> **Naming:** the project/repository is **OrbitalPV**. Existing Python workspace packages keep the explicit `space-pv-*` namespace to make their domain boundaries obvious.

## Foundation stack

- **pvlib** — tested PV equations and I-V/single-diode reference models behind a space-specific adapter.
- **Skyfield + python-sgp4** — Earth-orbit catalog propagation from CCSDS OMM/TLE.
- **Astropy** — time, units, frames and baseline solar-system coordinates.
- **SpiceyPy / NASA SPICE** — mission-grade ephemeris, attitude, clocks and frame transforms.
- **SpacePy / later radiation engines** — radiation/environment workstream.
- **HTTP connectors** — CelesTrak, Space-Track, NASA SSCWeb, NAIF, CDAWeb/HAPI, NOAA SWPC, SatNOGS DB and BIRDS EPS.

`poliastro` is intentionally not a core dependency because its upstream repository is archived.

## Repository map

```text
orbital-pv/
├── apps/
│   ├── space-pv-cli/
│   ├── space-pv-api/             # FastAPI application/API boundary
│   └── space-pv-web/             # React + TypeScript + Vite frontend
├── packages/
│   ├── space-pv-core/             # domain contracts/constants
│   ├── space-pv-orbit/            # orbit, Sun, eclipse, AOI, SPICE/Skyfield adapters
│   ├── space-pv-pvmodel/          # pvlib-backed spacecraft PV reference models
│   ├── space-pv-space-env/        # AM0/radiation/environment models
│   ├── space-pv-connectors/       # real external satellite/environment data
│   ├── space-pv-analytics/        # KPIs, residuals, anomalies, degradation
│   ├── space-pv-storage/          # DuckDB + PostgreSQL persistence
│   └── space-pv-orchestration/    # Celery queues/tasks; Redis broker
├── labs/
│   ├── 00_birds_baseline/
│   ├── 01_orbit_sun_geometry/
│   └── 02_pvlib_reference/
├── data/{raw,bronze,silver,gold}/
├── compose.yaml                  # Postgres + Redis + API + worker + Flower + React
├── docs/
└── tests/
```

## Install

```bash
uv sync --group dev --group lab --group orbit --group pv --group space --group app
uv run pytest
uv run ruff check .
uv run ty check
```

## Science pipeline

```text
real orbit/telemetry/environment data
              |
              v
      canonical time + frames
              |
    +---------+----------+
    |                    |
orbit + Sun          PV telemetry
    |                    |
    v                    |
eclipse + AOI + AM0      |
    |                    |
    +----------+---------+
               v
      expected PV performance
               |
               v
       residual / degradation
               |
               v
      anomaly + EOL analytics
```

See `docs/foundation_stack.md`, `docs/connectors/catalog.md`, `docs/architecture.md` and `docs/state_of_art.md`.


## Application platform

The web/application layer is intentionally separated from the scientific packages:

- **React + TypeScript + Vite** — frontend application.
- **FastAPI** — API and job submission boundary.
- **PostgreSQL** — durable multi-user/transactional application state and job metadata.
- **DuckDB** — local analytics, parquet-backed research datasets and fast time-series exploration.
- **Celery + Redis** — long-running ingestion, orbit, PV and analytics jobs.
- **Flower** — local Celery worker/task observability.

Start the development stack with:

```bash
docker compose up --build
```

Then open React on `http://localhost:5173`, FastAPI docs on `http://localhost:8000/docs`, and Flower on `http://localhost:5555`.

See `docs/application_platform.md`.


## Space GIS and dynamic visualization

The platform now separates scientific orbital reference-frame state from Earth-fixed
GIS render products. PostGIS serves hot satellite positions, ground tracks, stations and
footprints; DuckDB/Parquet retain analytical history and chart rollups; CesiumJS renders
time-dynamic 3D orbital scenes. See `docs/space_gis_and_visualization.md`.

## Literature library

A curated, source-tagged literature library is maintained in [`docs/literature/`](docs/literature/README.md). It covers the 2026 state of the art in space-PV cells and arrays, mission-aware performance modelling, radiation/degradation, digital twins, telemetry/AI, and open flight datasets/APIs.


## Roadmap evidence

- `docs/literature/09_ieso_2026_workshop_roadmap.md` — 2026 IESO workshop targets translated into software requirements and research roadmap.
- `docs/product_feature_roadmap.md` — prioritized product epics derived from the literature and 2026 IESO workshop.
