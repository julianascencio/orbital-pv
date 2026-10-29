# Performance modelling and digital twins for spacecraft PV

_Last reviewed: 2026-09-09_

## 1. The model boundary

A terrestrial PV model usually starts near the module plane-of-array irradiance. A spacecraft PV model must start much earlier:

```text
ephemeris + time
      ↓
Sun vector + distance
      ↓
eclipse / penumbra
      ↓
spacecraft attitude + panel normal
      ↓
AOI / shadowing
      ↓
AM0 spectral irradiance
      ↓
panel temperature
      ↓
radiation / aging state
      ↓
cell + string + array I-V
      ↓
MPPT / regulator / bus operating point
      ↓
measured power
```

The repository should preserve each intermediate state so a residual can be explained rather than merely observed.

## 2. NASA SPACE / Artemis: mission-aware EPS modelling

NASA's public Artemis presentation is a useful state-of-practice anchor. The SPACE model is used for EPS performance analysis on Orion and Gateway/PPE-related systems. The key point for this project is that power generation is evaluated under **mission events**, including eclipse, maneuvers, constrained pointing and radiation exposure.

This validates our decision to keep orbit/attitude/environment and PV models as separate packages joined at runtime.

## 3. LEO telemetry-calibrated modelling

Mohamed et al. (2025) provide an open-access example of a modelling environment for a body-mounted GaAs solar array using real-time telemetry from a LEOS-50 platform. The work combines mission design, illumination, thermal behavior, EPS considerations and telemetry validation.

This is a direct precedent for a first end-to-end lab:

```text
propagated orbit
+ Sun/eclipse
+ thermal state
+ GaAs electrical model
+ telemetry
→ expected power vs measured power
```

## 4. Digital twin: ESA Cluster

ESA Cluster is one of the most relevant operational case studies because the mission's solar arrays experienced severe long-term radiation degradation and the spacecraft operated far beyond their initial design life.

Recent work evolves in three steps:

1. simplified physics-based degradation model;
2. calibration against flight monitoring data;
3. Bayesian uncertainty/model discrepancy and digital-twin integration.

The 2025 SpaceOps paper explicitly describes a digital-twin solution using a simplified physics model, Bayesian calibration, monitoring data and ML to forecast power evolution.

The central lesson is that **calibration is part of the operational model**, not a one-time preprocessing task.

## 5. Model discrepancy is a first-class quantity

Even a physically correct model structure will omit effects and carry parameter errors. The 2026 Cluster calibration work highlights Gaussian-process model discrepancy and Bayesian parameter inference.

For this repository we should distinguish:

```text
measurement = physics(theta) + systematic_discrepancy(x) + noise
```

rather than forcing `theta` to absorb every missing physical effect.

This is important for degradation forecasts: otherwise the model can fit historical telemetry while producing overconfident EOL predictions.

## 6. EPS operating point cannot be ignored

Solar-array output telemetry does not necessarily equal array maximum-power capability. Depending on the architecture, the operating point can be affected by:

- MPPT controller behavior;
- direct energy transfer (DET);
- sequential shunt regulators;
- battery state of charge;
- load demand;
- bus voltage constraints;
- protection/bypass elements.

A 6U CubeSat EPS digital-twin paper provides an open implementation-oriented example using triple-junction cell sections represented through a single-diode equivalent model.

Therefore our analytics should distinguish:

```text
P_available
P_mpp_expected
P_operating_expected
P_measured
```

## 7. Model hierarchy recommended for this repo

### L0 — geometric reference

```text
P = P_BOL × (r_AU^-2) × eclipse × max(cos(AOI), 0)
```

Use for tests and debugging only.

### L1 — temperature-corrected empirical array model

Add measured/modelled temperature and manufacturer coefficients.

### L2 — electrical cell/string model

Single-diode or technology-specific I-V with series/parallel strings and bypass/protection behavior.

### L3 — radiation-aware model

Add equivalent fluence / DDD state and coverglass/optical derates.

### L4 — calibrated digital twin

Infer uncertain parameters from telemetry and retain posterior uncertainty.

### L5 — discrepancy-aware hybrid twin

Physics + learned residual/discrepancy + operational state inference.

## 8. Validation metrics

Every model run should report more than RMSE:

- MAE / RMSE / bias;
- orbit-integrated energy error;
- eclipse-entry/exit transient error;
- temperature-stratified error;
- AOI-stratified error;
- degradation slope error;
- uncertainty coverage / calibration;
- residual autocorrelation;
- transfer performance across satellites/time periods.

## Key references

- NASA, **Solar Array Performance Modeling for NASA's Artemis Missions**: https://ntrs.nasa.gov/citations/20240010780
- Mohamed et al. (2025), **Developing a modelling environment of spacecraft solar array in low Earth orbit using real-time telemetry data**, OA: https://doi.org/10.1016/j.fraope.2025.100268
- Open institutional copy: https://repository.msa.edu.eg/items/d725ab64-695a-4825-a7db-c391188af88e
- Antonello et al. (2025), **A Digital Twin Solution for Solar Arrays Degradation Assessment and Power Production Prediction: Application to ESA Cluster Mission**, open paper: https://publications.spaceops.org/2025/download_by_id.php?id=0013
- Sgorlon Gaiatto et al. (2025), **A novel physics-based computational framework to model spacecraft solar array power under degradation**, DOI: https://doi.org/10.1016/j.actaastro.2024.10.052
- **Implementation of a 6U CubeSat Electrical Power System Digital Twin** (2024, OA): https://www.mdpi.com/2226-4310/11/8/688
- **Simple solar panels/battery modeling for spacecraft power distribution systems** (2021): https://doi.org/10.1016/j.actaastro.2020.10.036
