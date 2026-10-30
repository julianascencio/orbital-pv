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
- AI-generated code and text are reviewed and tested where practical, but validation is still evolving and is not yet deep or comprehensive across all models and examples;
- as with any AI-assisted work, generated code, explanations, parameter choices, or literature interpretations may contain mistakes and should be checked against the cited sources;
- generated outputs should be treated as research and engineering work in progress rather than independently validated scientific truth;
- for research, qualification, or mission-critical use, users should independently verify the underlying references, assumptions, numerical results, and validation evidence.

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

### Ground satellite imagery

The repository's ground-data API retrieves **Sentinel-2 Collection 1 imagery**
through Earth Search and **solar/wind features from OpenStreetMap** through
Overpass. Search by bounding box, dates and scene cloud cover, read a small area
from a Cloud-Optimized GeoTIFF, and export raw pixels with their CRS, calibration
metadata and provenance. Neither service requires an API key.

Install the new, unreleased API with the optional raster reader:

```bash
python -m pip install "orbital-pv[ground,examples] @ git+https://github.com/julianascencio/orbital-pv.git"
```

See the [ground imagery guide](https://julianascencio.github.io/orbital-pv/user_guide/modeling_topics/ground_imagery.html)
and the real-image gallery examples for
[Cestas, France](https://julianascencio.github.io/orbital-pv/gallery/ground_imagery/plot_ground_satellite_inputs.html)
and [Rinconada near Rengo, Chile](https://julianascencio.github.io/orbital-pv/gallery/ground_imagery/plot_rengo_solar_plant.html).
The guide relates these inputs to [Dunnett et al. (2020)](https://doi.org/10.1038/s41597-020-0469-8):
the paper starts from OSM features; satellite imagery adds inspection context.
Farm clustering, GHSL filtering and capacity calibration are separate methodology steps.

## Foundation stack

- **pvlib** — tested PV equations and I-V/single-diode reference models behind a space-specific adapter.
- **Skyfield + python-sgp4** — Earth-orbit catalog propagation from CCSDS OMM/TLE.
- **Astropy** — time, units, frames and baseline solar-system coordinates.
- **SpiceyPy / NASA SPICE** — mission-grade ephemeris, attitude, clocks and frame transforms.
- **SpacePy / later radiation engines** — radiation/environment workstream.
- **HTTP connectors** — CelesTrak, Space-Track, NASA SSCWeb, NAIF, CDAWeb/HAPI, NOAA SWPC, SatNOGS DB and BIRDS EPS.
- **Ground inputs** — Earth Search Sentinel-2 Collection 1 COGs and OpenStreetMap solar/wind features, with optional Rasterio window reads.

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

## PV modelling and loss analytics

OrbitalPV 0.7 explains **expected power minus actual power** with an explicit
loss ledger. `pvwatts_loss_chain` exposes cumulative physical and controller
predictions; `power_loss_breakdown` turns their differences into named stages
and categories; `summarize_power_losses` reports observed-time energy in Wh.

The categories cover solar resource, eclipse/pointing, optics/spectrum, cell
temperature, radiation/aging, mismatch/wiring, conversion, operations, and an
unexplained residual. Every attributed stage carries an evidence description.
Gains keep their sign, multiplicative losses are not added as independent
percentages, and energy accounting excludes missing samples and long gaps.

Choose an ideal reference for a design budget or a healthy operating model
for underperformance analysis. Normal eclipse and temperature effects already
included in the operating expectation must not be counted twice. V×I telemetry
alone does not establish available maximum power or the cause of a shortfall.

The [PV-analytics gallery](https://julianascencio.github.io/orbital-pv/gallery/pv_analytics/index.html)
contains a physical spacecraft loss budget, a two-array operating diagnostic,
and a held-out reference comparison using real Flying Laptop measurements.
See the [loss-analysis guide](https://julianascencio.github.io/orbital-pv/user_guide/modeling_topics/pv_loss_analysis.html)
for equations, evidence requirements and reusable code.

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
