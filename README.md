# OrbitalPV

<p align="center">
  <a href="https://asvaconsulting.com">
    <img
      src="https://asvaconsulting.com/wp-content/uploads/2022/05/ASVA-1-1-scaled.jpg"
      alt="ASVA Consulting"
      width="280"
    />
  </a>
</p>

<p align="center">
  <strong>Created by ASVA Consulting</strong><br>
  <a href="https://asvaconsulting.com">asvaconsulting.com</a><br>
  <a href="mailto:contacto@asvaconsulting.com">contacto@asvaconsulting.com</a>
</p>

Created by **ASVA Consulting**, OrbitalPV is an open-source full-stack lab for **spacecraft photovoltaic performance analytics**: PV physics, orbit/Sun geometry, real spacecraft data connectors, degradation/anomaly analytics, reproducible research labs, and a web application platform.

The structure follows a modular separation-of-concerns approach: domain models, physics engines, connectors and analytics are independent workspace packages with consistent quality tooling.

## AI-assisted development and literature basis

A substantial part of the code, documentation, examples, tests, and repository scaffolding in OrbitalPV is generated or drafted with AI assistance.

The scientific direction is **not intended to come from unsourced model invention**. Repository developers choose the specific papers, standards, datasets, technical reports, and other literature used to define the physical assumptions, reference values, methods, examples, and research roadmap. AI is then used to accelerate implementation, synthesis, documentation, testing, and iteration around that selected evidence base.

In practice:

- source literature and technical references are selected by the repository developers;
- model assumptions and numerical baselines should be traceable to cited literature, public datasets, or explicitly documented engineering assumptions;
- AI-generated code and text are reviewed, tested, and corrected by human contributors before being treated as part of the project;
- generated outputs should not be interpreted as independently validated scientific truth merely because they are present in the repository;
- for research, qualification, or mission-critical use, users should verify the underlying references, assumptions, and validation evidence.

The curated evidence base is maintained in `docs/literature/` and in the references attached to individual methods and examples.

## Install from PyPI

```bash
python -m pip install orbital-pv
```

Use the public API as:

```python
import orbitalpv as opv

positions_m = opv.circular_orbit_positions_m(
    altitude_m=550_000.0,
    inclination_deg=51.6,
)

g_am0 = opv.am0_irradiance(opv.ASTRONOMICAL_UNIT_M)
```

Optional extras:

```bash
python -m pip install "orbital-pv[examples]"
python -m pip install "orbital-pv[orbit]"
python -m pip install "orbital-pv[full]"
```

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
├── src/orbitalpv/                 # public PyPI API
├── apps/
│   ├── space-pv-cli/
│   ├── space-pv-api/
│   └── space-pv-web/
├── packages/
│   ├── space-pv-core/
│   ├── space-pv-orbit/
│   ├── space-pv-pvmodel/
│   ├── space-pv-space-env/
│   ├── space-pv-connectors/
│   ├── space-pv-analytics/
│   ├── space-pv-storage/
│   └── space-pv-orchestration/
├── examples/
├── labs/
├── data/{raw,bronze,silver,gold}/
├── docs/
└── tests/
```

The `space_pv_*` packages remain available as lower-level implementation modules for contributors and advanced use, while `orbitalpv` is the stable user-facing import.

## Documentation

**https://julianascencio.github.io/orbital-pv/**

The documentation uses Sphinx, PyData Sphinx Theme, and Sphinx-Gallery. Gallery examples execute during the documentation build and use the same `orbitalpv` API installed from PyPI.

Build locally:

```bash
make docs
```

## Development

```bash
uv sync --all-packages --group dev --group lab --group orbit --group pv --group space --group app
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

## Space GIS and dynamic visualization

The platform separates scientific orbital reference-frame state from Earth-fixed GIS render products. PostGIS serves hot satellite positions, ground tracks, stations and footprints; DuckDB/Parquet retain analytical history and chart rollups; CesiumJS renders time-dynamic 3D orbital scenes. See `docs/space_gis_and_visualization.md`.

## Literature library

A curated, source-tagged literature library is maintained in [`docs/literature/`](docs/literature/README.md). It covers the 2026 state of the art in space-PV cells and arrays, mission-aware performance modelling, radiation/degradation, digital twins, telemetry/AI, and open flight datasets/APIs.

## Roadmap evidence

- `docs/literature/09_ieso_2026_workshop_roadmap.md` — 2026 IESO workshop targets translated into repository features and R&D priorities.
- `docs/product_feature_roadmap.md` — prioritized product epics derived from the literature and 2026 IESO workshop.

## Creator and contact

OrbitalPV is created and maintained by **ASVA Consulting**.

- Website: https://asvaconsulting.com
- Contact: contacto@asvaconsulting.com
