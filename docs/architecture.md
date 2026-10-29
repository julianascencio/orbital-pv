# Architecture

## Design principles

1. **Physics first, ML on residuals.**
2. **Time/frame/unit provenance is mandatory.** A correct number in the wrong frame is a wrong result.
3. **Separate raw telemetry/catalog data from derived science products.**
4. **Every experiment is reproducible from config + seed + input manifest.**
5. **Mission connectors do not contain analytics logic.**
6. **PV equations do not own orbit or radiation logic.**
7. **Use recognized upstream engines behind thin adapters; keep our domain contracts stable.**
8. **Never silently mix ephemerides, coordinate frames, timestamps or irradiance references.**

## Workspace packages

### `space-pv-core`
Stable domain contracts and physical constants. Keep small and dependency-light.

### `space-pv-orbit`
Orbit and Sun geometry. Primary Earth-catalog route is Skyfield + Vallado SGP4 from OMM. Astropy provides baseline Sun vectors/time/coordinate support. SpiceyPy is the mission-grade route for SPK/CK/FK/SCLK kernels. Owns eclipse, spacecraft-to-Sun geometry and panel incidence geometry.

### `space-pv-pvmodel`
PV equations behind a space adapter. Reuses pvlib PVWatts and single-diode/De Soto where physically appropriate. Does **not** pretend terrestrial ModelChain is a spacecraft model. III-V multi-junction, radiation-driven parameter evolution and string/network behavior are separate extensions.

### `space-pv-space-env`
AM0 irradiance and later radiation/plasma/thermal environment state. Environment state must be aligned to orbit state before feeding the PV model.

### `space-pv-connectors`
Raw external data adapters: BIRDS EPS, CelesTrak, Space-Track, NASA SSCWeb, NASA CDAWeb/HAPI, NASA NAIF, NOAA SWPC and SatNOGS DB. ESA DISCOS is next for physical/object metadata. Every retrieval should produce source/query/timestamp/checksum provenance.

### `space-pv-analytics`
Expected-vs-measured residuals, KPIs, anomaly detection, degradation estimation, uncertainty and later RUL/EOL.

### `space-pv-cli`
Reproducible orchestration only; no science logic.

## Canonical data flow

```text
RAW external artifact
  -> BRONZE normalized source table (units/time/frame explicit)
  -> SILVER synchronized physical state
       orbit_state
       sun_geometry
       space_environment
       pv_telemetry
       expected_pv
  -> GOLD KPIs/anomalies/degradation/EOL
```

## Expected-power progression

### M0 — telemetry-only
Upper-envelope baseline and gross fault detection.

### M1 — orbit/Sun geometry

`G_eff = G_AM0(r_sun) * illumination * max(cos(AOI), 0)`

### M2 — calibrated PV physics

`P_expected = PV(G_eff, T_cell, BOL parameters)`

pvlib-backed PVWatts/single-diode is the first reference implementation.

### M3 — radiation state

Electrical parameters evolve from dose/fluence/NIEL/DDD with uncertainty.

### M4 — electrical network

Strings, cell mismatch, bypass/protection diodes, MPPT/BCR and self-shadowing.

### M5 — hybrid calibrated model

Estimate uncertain physical parameters against flight telemetry; ML acts on model residuals and uncertainty rather than raw power alone.

## Reproducibility contract

Each serious lab run writes:

```text
outputs/<run_id>/
  config.json
  input_manifest.json
  metrics.json
  events.parquet
  logs.jsonl
  figures/
```

`input_manifest.json` must include upstream source, query/URL, retrieval timestamp, checksum, reference frame, time scale, units and licensing/attribution constraints where applicable.

## Application platform boundaries

### `space-pv-storage`
Persistence adapters only. PostgreSQL owns transactional/shared application state; DuckDB owns local analytical datasets and research outputs. Storage models must not contain PV/orbit business logic.

### `space-pv-orchestration`
Celery configuration, queue routing and task wrappers. Science packages never import Celery. Workloads are routed to `ingestion`, `orbit`, `pv` and `analytics` queues so concurrency and resource policies can evolve independently.

### `space-pv-api`
FastAPI HTTP boundary for the React app and automation clients. It validates requests, persists durable job metadata, submits Celery work and exposes job state. It does not implement science equations.

### `space-pv-web`
React + TypeScript + Vite frontend. Data fetching is API-driven; no direct database or connector access from the browser.

## Application execution flow

```text
React
  -> FastAPI
      -> PostgreSQL: create durable JobRun
      -> Redis/Celery: enqueue task
          -> worker
              -> connectors / orbit / PV / analytics packages
              -> DuckDB / Parquet analytical outputs
              -> PostgreSQL: update JobRun/result metadata
  <- FastAPI job/query endpoints
```

For development, `compose.yaml` starts PostgreSQL, Redis, FastAPI, Celery worker, Flower and React. Before production, replace `Base.metadata.create_all()` with explicit Alembic migrations and split workers by queue/resource profile.
