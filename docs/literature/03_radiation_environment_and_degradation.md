# Radiation environment and PV degradation

_Last reviewed: 2026-09-09_

## 1. Why radiation must be a state variable

Radiation-induced degradation is strongly orbit-, shielding-, particle- and energy-dependent. A fixed annual percentage is useful for high-level sizing but is not sufficient for performance analytics or anomaly attribution.

The recommended chain is:

```text
trajectory
   ↓
trapped + solar + cosmic particle environment
   ↓
energy-resolved spectrum / fluence
   ↓
shielding / coverglass
   ↓
NIEL / DDD / equivalent fluence
   ↓
cell parameter degradation
   ↓
array power loss
```

## 2. Near-Earth environment: IRENE / AE9 / AP9 / SPM

IRENE combines modern trapped energetic electron (AE9), proton (AP9) and plasma (SPM) specification models. AFRL describes the model as being built from dozens of satellite datasets and capable of returning statistical confidence intervals for flux/fluence and dose-like derived quantities.

Important modelling implication: the environment is **probabilistic**, not a deterministic lookup table. The repository should preserve percentile/scenario information when generating EOL distributions.

ESA exposes IRENE through its Network of Models / SPENVIS ecosystem, making it a good integration target for the `space-pv-space-env` package.

## 3. NIEL and displacement damage dose

Non-ionizing energy loss (NIEL) is the key bridge between incident particle energy and displacement damage in semiconductor materials. Equivalent-fluence methods and displacement damage dose (DDD) remain common engineering techniques for mapping complex proton/electron spectra into solar-cell degradation.

Recent 2025 open-access work continues to quantify semiconductor damage across LEO, MEO and GEO using NIEL/DDD methods, while the 2021 III-V review remains a useful compact history of electron/proton degradation models.

For implementation, keep these layers separate:

```python
particle_environment(...)
shielding_transport(...)
niel(material, energy)
ddd(...)
cell_degradation(ddd, technology, temperature, ...)
```

This makes it possible to replace one environment or device-response model without rewriting the entire chain.

## 4. Radiation is not the only long-term degradation source

Power loss can also arise from:

- coverglass/adhesive darkening;
- UV exposure;
- atomic oxygen in LEO;
- contamination;
- thermal cycling;
- micro-meteoroid/debris impacts;
- harness/interconnect faults;
- failed strings or protection components;
- regulator/MPPT changes.

The analytics problem is therefore an **attribution problem**. Radiation exposure can explain a long-term trend but should not automatically be assigned as the cause of every residual loss.

## 5. Strong flight evidence: Cluster and MEO arrays

ESA Cluster is a valuable example because severe long-duration degradation correlated with intense radiation environments and Van Allen belt passages had real operational consequences. The current digital-twin literature uses this mission to calibrate power-degradation models.

A 2025 open-access paper on a triple-junction GaAs array after seven years in MEO is another useful reference for combining theoretical radiation design and on-orbit life prediction.

## 6. Emerging technologies complicate the damage model

Perovskites can show unusual radiation tolerance and partial recovery/self-healing behaviors under some conditions, so simply reusing silicon or GaAs degradation constants is invalid. Ultrathin silicon also shows thickness- and annealing-dependent radiation behavior. The technology type must therefore be encoded explicitly in degradation models.

## 7. Recommended data products

### Bronze
- radiation model raw outputs;
- external space-weather data;
- orbit/ephemeris used for environment query.

### Silver
- electron/proton differential flux by energy;
- cumulative fluence;
- shielding configuration;
- DDD / equivalent fluence by technology.

### Gold
- expected retained `Isc`, `Voc`, `Pmp`;
- radiation-only power derate;
- uncertainty quantiles;
- event attribution windows.

## 8. Research experiments

1. Compare a constant `%/year` derate against DDD-driven degradation for several LEO/MEO/GEO orbits.
2. Quantify sensitivity to shield/coverglass thickness.
3. Compare deterministic median environment with Monte-Carlo/percentile EOL power.
4. Align BIRDS or other telemetry with geomagnetic/solar events and test whether residual shifts are detectable.
5. Separate sudden faults from cumulative radiation using change-point models plus exposure state.

## Open / public references

- AFRL **IRENE-AE9/AP9/SPM factsheet**: https://www.vdl.afrl.af.mil/programs/ae9ap9/factsheet.php
- AFRL **IRENE documents and Python API references**: https://www.vdl.afrl.af.mil/programs/ae9ap9/documents.php
- ESA Network of Models — IRENE: https://nom.esa.int/models/irene
- **Semiconductor Material Damage Mechanisms Due to Non-Ionizing Energy in Space-Based Solar Systems** (2025, OA): https://www.mdpi.com/1996-1073/18/3/509
- **A short review of radiation-induced degradation of III–V photovoltaic cells for space applications** (2021, OA): https://doi.org/10.1016/j.solmat.2021.111379
- **On-Orbit Life Prediction and Analysis of Triple-Junction Gallium Arsenide Solar Arrays for MEO Satellites** (2025, OA): https://www.mdpi.com/2226-4310/12/7/633
- ESA Cluster digital twin, open SpaceOps paper: https://publications.spaceops.org/2025/download_by_id.php?id=0013
- **Impact-induced failures of solar array cable bundles** (2025, OA; useful non-radiation fault reference): https://doi.org/10.1016/j.actaastro.2025.05.053
