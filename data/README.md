# Data

The repository does not vendor external mission datasets.

- `raw/`: untouched downloaded files
- `bronze/`: normalized schema/unit conversion
- `silver/`: enriched telemetry and physics-derived features
- `gold/`: KPIs/events/model outputs

Recommended first source: BIRDSOpenSource/EPS_dataset. Place `TSURU.xlsx`, `NEPALISAT.xlsx`, `RAAVANA.xlsx` or `UGUISU.xlsx` in `data/raw/`.
