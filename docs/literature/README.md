# Space PV literature library

_Last reviewed: 2026-10-03_

This folder is a curated, engineering-oriented literature library for **space photovoltaic performance analytics**. It is intentionally organized around the software architecture of this repository rather than around academic disciplines alone.

The library distinguishes three evidence levels:

- **Flight / operational evidence** — data or methods demonstrated on an actual spacecraft or flight experiment.
- **Ground / qualification evidence** — laboratory radiation, thermal, vacuum, electrical, or mechanical validation relevant to space use.
- **Review / synthesis** — literature reviews, state-of-the-art reports, standards guidance, and model documentation.

It also distinguishes access status:

- **OPEN** — full text or authoritative public report is freely accessible.
- **PUBLIC-DATA** — dataset/API/software documentation is openly accessible.
- **WATCH** — important current paper, but the repository does not assume unrestricted full-text access.

No copyrighted papers are copied into this repository. The library stores **citations, links, technical notes, and research implications**. Public-domain or openly licensed source files may be mirrored later in a dedicated `docs/library/assets/` folder if their licenses are checked first.

## Reading order

1. [00_current_state_of_art_2026.md](00_current_state_of_art_2026.md) — concise synthesis of where the field is now.
2. [01_cells_arrays_and_specific_power.md](01_cells_arrays_and_specific_power.md) — III-V, IMM, thin films, flexible arrays, perovskites and ultrathin silicon.
3. [02_performance_modelling_and_digital_twins.md](02_performance_modelling_and_digital_twins.md) — expected-power models, telemetry calibration and digital twins.
4. [03_radiation_environment_and_degradation.md](03_radiation_environment_and_degradation.md) — NIEL, DDD, equivalent fluence, IRENE and degradation modelling.
5. [04_telemetry_ai_and_health_monitoring.md](04_telemetry_ai_and_health_monitoring.md) — anomaly detection, physics-informed ML and remaining useful life.
6. [05_open_data_and_reproducible_sources.md](05_open_data_and_reproducible_sources.md) — datasets, APIs and sources that can drive reproducible experiments.
7. [06_research_gaps_and_repo_backlog.md](06_research_gaps_and_repo_backlog.md) — research questions translated directly into repository work.
8. [07_frontier_watch_2026.md](07_frontier_watch_2026.md) — late-2026 papers and methods not yet treated as settled practice.
9. [08_space_based_solar_power_market_and_datacenters.md](08_space_based_solar_power_market_and_datacenters.md) — SBSP commercial context, Virtus Solis/Brae PPA, datacenter use case and analytics implications.
10. [09_ieso_2026_workshop_roadmap.md](09_ieso_2026_workshop_roadmap.md) — DOE IESO workshop targets translated into repository features, schemas and R&D priorities.
11. [open_library.md](open_library.md) — master reading list with access status and relevance.

## Scope

The core subject is not simply solar-cell materials. The repository targets the full chain:

```text
orbit + attitude + Sun + eclipse
            ↓
space environment + radiation + temperature
            ↓
cell / string / array electrical model
            ↓
EPS operating mode + MPPT / regulation
            ↓
expected power / energy
            ↓
telemetry-normalized residuals
            ↓
degradation / anomaly / RUL / mission margin
```

That system-level focus is what separates this project from a terrestrial PV analytics stack.
## Implemented 2026 expansion

See [the implementation and evidence matrix](10_2026_implementation_matrix.md)
for the methods, connectors, executable analyses and validation limits added to
the source tree from the selected 2024–2026 research.
