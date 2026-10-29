# Case 0 — BIRDS telemetry baseline

## Question
Can a lightweight, explainable baseline identify persistent PV under-performance from panel telemetry before we introduce orbit and radiation models?

## Inputs
At minimum: timestamp, panel voltage, panel current. Temperature is retained when available.

## Outputs
- power time series
- normalized power against robust reference
- robust anomaly score
- anomaly fraction / event candidates
- linear long-term normalized-power degradation slope

## Run

```bash
uv run --package space-pv-cli space-pv case0 --demo
uv run --package space-pv-cli space-pv case0 --input data/raw/TSURU.xlsx
```

## Important limitation
Case 0 is deliberately **not** a physically normalized spacecraft PV model. Attitude, eclipse, solar distance, thermal response and radiation are confounders. The purpose is to validate ingestion, reproducibility, panel-level KPIs and event plumbing before physics layers are added.
