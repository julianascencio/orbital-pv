# Telemetry, AI and health monitoring for spacecraft PV

_Last reviewed: 2026-09-09_

## 1. The key analytics principle

Raw power is a poor anomaly signal when expected power changes dramatically every orbit. The preferred signal is a physics-normalized residual:

```text
residual(t) = P_measured(t) - P_expected(t | orbit, Sun, attitude, T, radiation, EPS mode)
```

or a normalized ratio where appropriate.

This removes deterministic orbital structure before anomaly detection and makes results easier to interpret.

## 2. Open telemetry evidence: BIRDS

The BIRDS EPS dataset remains the strongest fully open starting point for this repository. It contains panel and battery voltage/current/temperature measurements from four 1U CubeSats. Two spacecraft exhibit panel failures, providing rare real labels for fault/degradation studies.

Sampling is typically every 90 s in nominal operation and can reach 10 s in high-sampling mode. The data are available through both a public GitHub repository and Mendeley Data, with an open Data in Brief article describing acquisition and labels.

The limitation is equally important: BIRDS does not provide every state needed for a high-fidelity digital twin at every timestamp. Orbit/attitude/environment must be reconstructed or treated probabilistically.

## 3. Generic spacecraft telemetry anomaly detection

The 2024 explainable-anomaly paper on NASA spacecraft telemetry shows the broader direction of the field: richer feature extraction, non-linear models, and explainability rather than fixed limits alone. A 2025 open review surveys deep-learning and graph/temporal approaches and notes strong results but also dataset and generalization limitations.

For PV, generic anomaly models should be used **after** physical normalization where possible.

## 4. Hybrid model + data is becoming the operational direction

NASA's 2025 work on space power systems explicitly combines model-based and data-driven techniques for fault/anomaly monitoring. ESA's Cluster work similarly combines physics models, calibration, ML and operational telemetry.

This supports a layered architecture:

```text
physics residual
   ↓
robust statistics / change point
   ↓
interpretable ML
   ↓
sequence / graph models only when justified
```

rather than starting with a transformer over raw telemetry.

## 5. Physics-informed ML frontier

A 2026 paper on TSURU telemetry develops a physics-informed ML method for panel temperature, voltage and current using limited on-orbit telemetry. The method includes energy-balance and PV I-V constraints rather than learning the mapping freely.

Even where full text is not guaranteed open, the result is important as a research-frontier signal: **PIML is moving directly into spacecraft solar-panel prediction**, not only generic spacecraft health management.

## 6. Remaining useful life should be probabilistic

For long-lived arrays, a useful RUL output is not:

```text
failure date = 2031-05-12
```

It is closer to:

```text
P(EOL power margin < 0 by date t)
```

with explicit uncertainty from:

- environment scenario;
- degradation parameters;
- measurement noise;
- model discrepancy;
- unknown operational state;
- future mission profile.

Bayesian calibration in the Cluster work is therefore particularly relevant.

## 7. Feature families for PV health analytics

### Physics residual features
- `P_meas / P_expected`;
- residual energy per sunlit orbit;
- temperature-normalized residual;
- AOI-stratified residual;
- eclipse-recovery residual.

### Electrical topology features
- panel-to-panel imbalance;
- inferred failed-string fraction;
- `Voc`/`Isc` proxy shifts when available;
- MPPT operating-point deviations;
- battery/array coupling signatures.

### Degradation features
- robust rolling upper envelope;
- slope vs time;
- slope vs DDD/equivalent fluence;
- persistent change-point magnitude;
- posterior retained-power distribution.

### Context features
- eclipse state;
- attitude mode;
- orbital region;
- radiation event indicators;
- thermal cycle phase;
- spacecraft operational mode.

## 8. Benchmarking rules

To avoid misleading ML results:

1. Split by **time and spacecraft**, not random rows.
2. Prevent future orbit/radiation information from leaking into training features.
3. Benchmark against a simple robust residual threshold and change-point detector.
4. Report false alarms per day/orbit, not just F1.
5. Evaluate anomaly lead time.
6. Require explanation output tied to physical variables.
7. Test transfer to another panel/satellite where possible.

## Open / public references and data

- BIRDS EPS dataset GitHub: https://github.com/BIRDSOpenSource/EPS_dataset
- BIRDS Mendeley dataset: https://data.mendeley.com/datasets/8kp25ycf63/1
- BIRDS Data in Brief article (OA): https://pmc.ncbi.nlm.nih.gov/articles/PMC9679683/
- **Explainable anomaly detection in spacecraft telemetry** (2024, OA): https://doi.org/10.1016/j.engappai.2024.108083
- **A Review of Anomaly Detection in Spacecraft Telemetry Data** (2025, OA): https://www.mdpi.com/2076-3417/15/10/5653
- NASA **A Hybrid Model and Data Driven Approach for Anomaly Detection in Space Power Systems** (2025, public): https://ntrs.nasa.gov/citations/20250005402
- **Synthetic satellite telemetry data for machine learning** (2025, OA): https://link.springer.com/article/10.1007/s12567-024-00589-1
- ESA Cluster digital twin, open paper: https://publications.spaceops.org/2025/download_by_id.php?id=0013

## Frontier watch

- **Telemetry-driven physics-informed prediction for on-orbit thermal–electrical performance of solar panels in satellite power system** (2026): https://doi.org/10.1016/j.ast.2026.112268
- **Towards a robust calibration and model discrepancy reduction for digital twin spacecraft: application to ESA Cluster mission** (2026): https://doi.org/10.1016/j.ast.2025.110769
