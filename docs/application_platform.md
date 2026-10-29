# Application platform

The repository separates scientific computation from application infrastructure.

## Runtime components

```text
React / Vite
    |
    v
FastAPI ----------------------> PostgreSQL
    |                             operational metadata
    | enqueue
    v
Redis broker <---------------- Celery workers
                                  |
                 +----------------+----------------+
                 |                |                |
              connectors        orbit/PV        analytics
                 |                |                |
                 +----------------+----------------+
                                  |
                                  v
                               DuckDB
                       local analytical store
```

## Storage responsibilities

### PostgreSQL
Use PostgreSQL for multi-user, transactional application state:

- users/organizations later
- satellites and missions selected by users
- data-source configuration
- job definitions and job execution history
- model/run metadata
- annotations, alarms and workflow state

### DuckDB
Use DuckDB for local analytical work and reproducible labs:

- raw/normalized telemetry query acceleration
- derived time-series features
- experimental outputs
- parquet-backed Bronze/Silver/Gold datasets
- local development with no database service required

DuckDB is not the queue or source of truth for shared application state.

## Job orchestration

Celery is an application-layer dependency only. Science packages never import Celery.
Queues are separated by workload type:

- `ingestion`: remote API and telemetry ingestion
- `orbit`: propagation, SPICE and geometry
- `pv`: PV modelling and I-V calculations
- `analytics`: residual, anomaly and degradation jobs

Redis is used as broker/result backend in development. Postgres persists durable domain/job metadata.

## Frontend

`apps/space-pv-web` is React + TypeScript + Vite with TanStack Query. The initial shell exposes logical product areas for satellites, orbit, PV performance, telemetry, jobs and labs.
