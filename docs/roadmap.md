# Roadmap

## Phase 0 — repository foundation (implemented)
- uv workspace
- Ruff + ty + pytest
- core satellite/orbit/attitude/telemetry contracts
- deterministic synthetic PV telemetry baseline
- data lake folders + state-of-art document

## Phase 1 — physical foundation (implemented skeleton, now hardening)
- pvlib adapter package
- Skyfield + Vallado SGP4 adapter
- Astropy Sun/time/frame adapter
- SpiceyPy adapter
- Earth eclipse / penumbra geometry
- panel normal + quaternion attitude transforms
- AM0 + AOI effective irradiance
- CelesTrak, Space-Track, SSCWeb, NAIF, CDAWeb, NOAA SWPC, SatNOGS and BIRDS connectors

Exit criterion: reproduce one satellite orbit/Sun/eclipsing timeline and one expected-PV timeline end to end with a versioned input manifest.

## Phase 2 — real-flight benchmark
- BIRDS exact workbook mappings and Parquet bronze layer
- select 2-3 SatNOGS missions exposing useful EPS + ADCS telemetry
- align decoded telemetry with orbit and Sun state
- expected-vs-measured PV residual
- known-failure benchmark
- precision/recall, detection delay and false-alarm metrics

## Phase 3 — spacecraft PV physics
- BOL cell/panel parameter registry
- III-V multi-junction model (current matching, spectral response)
- measured or radiative thermal model
- string topology / blocking-bypass-protection diodes
- BCR/MPPT operating-state model

## Phase 4 — radiation/environment
- AE9/AP9 or SPENVIS output connector
- NOAA/GOES event context
- NIEL tables / equivalent fluence / DDD
- coverglass/shielding parameters
- parameter degradation laws with uncertainty
- storm/event attribution

## Phase 5 — diagnostics and EOL/RUL
- panel/string failure inference
- self-shadow/mismatch/reverse-bias signatures
- change-point detection
- Bayesian/ensemble degradation forecast
- confidence bounds and mission power-margin risk

## Phase 6 — technology and business benchmark
- III-V vs Si vs thin-film/perovskite mission profiles
- Wh/kg, W/m2 and delivered-energy KPIs
- degradation-adjusted mission value
- scalability/runtime benchmarks
- reproducibility artifacts suitable for challenge/publication review

## Application platform foundation (implemented skeleton)
- React + TypeScript + Vite application shell
- FastAPI API boundary
- PostgreSQL operational/job metadata model
- DuckDB analytical telemetry/derived-metric store
- Celery + Redis background execution
- workload queues: ingestion, orbit, pv, analytics
- Flower development observability
- Docker Compose development stack

Next hardening steps:
- Alembic migrations and richer satellite/mission/source schemas
- concrete Celery workflows calling connectors/orbit/PV packages
- idempotency, retries, timeouts and per-satellite locks
- structured run logs and provenance persisted with every job
- frontend orbit map, telemetry explorer and expected-vs-measured PV pages
- auth/organization tenancy only when external users are introduced

## Workshop-driven product requirements (IESO Space PV Workshop 2026)

The 2026 IESO workshop adds several concrete requirements that should cut across the phases above:

- explicit hardware boundary (`cell`, `CIC`, `panel/blanket`, `array`, `spacecraft_bus`) for every performance and cost metric;
- mandatory BOL/EOL, AM0/AM1.5, mission-duration, orbit-profile and source metadata;
- mission environment profiles for LEO, MEO, GEO, cislunar and lunar use cases;
- technology registry spanning III-V, silicon and perovskite/thin-film families;
- combined-stressor test datasets rather than isolated radiation-only qualification records;
- recovery / annealing / metastability support in degradation models;
- qualification-evidence and ground-test ↔ flight-data registries;
- mission × technology capability matrix and technoeconomic trade-space analysis;
- workshop target dashboard for array-level `W/kg`, EOL `W/m²`, retained BOL power and cost/W.

### New exit criterion for the scientific foundation

For any modeled or measured performance number, the repository should be able to answer:

```text
What technology?
What hardware boundary?
What illumination reference?
BOL or EOL?
What orbit / mission profile?
What stressor history?
What source / test / flight evidence?
What uncertainty?
```

If those questions cannot be answered, the metric is not decision-grade.
