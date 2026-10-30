# Environmental inputs and Earth-view benchmark

This analysis combines two **separate** checks: actual NOAA MetOp-01 detector
observations on 2023-01-01 and an independent analytic Earth-view scenario.
No observed particle channel is converted to solar-cell damage without a
mission-specific spectrum, angular response, shielding and calibrated NIEL model.

Run offline after the standard development install:

```bash
PYTHONPATH=src uv run python analysis/environmental_inputs/run.py
```

`data/metop01_20230101_minutes.csv` contains UTC-minute medians, channel-specific
valid counts, and first observed track coordinates. The public NOAA source has
43,199 native records. Its original units, processing-level metadata, source
URL, SHA-256 and reduction rule are in `data/provenance.json`. Negative provider
values are excluded from the median and counted as missing. Instrument
contamination remains uncorrected. The two channels have different energy
definitions and units and must not be added.

To re-download the pinned public source and regenerate the snapshot:

```bash
PYTHONPATH=src uv run python analysis/environmental_inputs/run.py --download
```

`reference_results.json` records an executed offline run. A uniform Lambertian
Earth at 240 W/m², radius R and observer radius r has nadir-plane irradiance
`240 * (R/r)**2`; the grid integration is compared with that independent result.
This is a numerical benchmark, **not measured CERES flux**.

`data/ceres_catalog.json` records a real public CMR discovery and one granule
for the same date. Reading the protected NASA file requires authorized Earthdata
access; no CERES observations are bundled or silently replaced with synthetic data.
Current CMR short names and versions are separate fields after the cloud migration.

Sources: [NOAA SEM-2](https://www.ncei.noaa.gov/products/poes-metop-space-environment-monitor),
[NASA CERES](https://ceres.larc.nasa.gov/data/),
[NASA CMR API](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html).
