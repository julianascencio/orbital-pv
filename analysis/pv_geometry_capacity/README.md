# Geometry and independently calibrated capacity

```bash
python -m pip install '.[ground-research,examples]'
python analysis/pv_geometry_capacity/run.py --output outputs/pv_geometry_capacity
```

The offline workflow uses the real historical Wiki Solar/OSM reference from
[Dunnett's Figshare archive v2](https://doi.org/10.6084/m9.figshare.11310269.v2),
verifying its recorded SHA-256. Positive finite capacity and area are required.
Spain is the final holdout. France, Canada and Italy supply separate interval
calibration; the remaining countries fit a log-linear area regression. These
groups are fixed before evaluation. No AC/DC basis is invented: this historical
table reports MW inconsistently, so estimates remain `reported` MW.

Absolute log residuals on 320 independent calibration records set a 90% nominal
split-conformal interval using the finite-sample order statistic. Country shift
violates the exchangeability assumption; actual test coverage is therefore
essential. On the bundled Spain records (n=159), MAE is 6.391 MW, RMSE 10.192 MW,
R² 0.535, and coverage **77.36%**, below nominal 90%. One prediction extrapolates
beyond fitting feature ranges and is flagged. Intervals omit image mapping error
and AC/DC-ratio uncertainty. These results are not directly pooled with an older
method's different exclusions, transformations and training split.

Geometry summaries from the real Cestas/Tenerife OSM snapshots measure polygon
footprint area and minimum-rectangle long-axis azimuth in local UTM. The axis is
ambiguous modulo 180 degrees. It is not panel facing azimuth or measured tilt.
An OSM land boundary remains a land/footprint proxy; it never becomes physical
module surface area. The public model can add independently available geometry
predictors and explicitly convert AC/DC with a caller-supplied ratio, but this
historical example cannot recover missing equipment metadata.

Outputs: `capacity_model.json`, `spain_capacity_holdout.csv`, `report.json`,
`capacity_coverage.png`, and geometry JSON with unchanged source properties.
Source licenses and checksum provenance are retained. Reference metrics are in
`reference_results.json`.
