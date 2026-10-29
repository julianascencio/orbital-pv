# Current state of the art — space PV performance analytics (2026)

_Last reviewed: 2026-10-03_

## Executive conclusion

The field is converging on **hybrid, mission-aware digital performance models**. The mature engineering baseline remains high-efficiency III-V multijunction solar arrays, but the research frontier is no longer defined by cell efficiency alone. The main system metrics are increasingly **end-of-life power, specific power, stowed volume, radiation tolerance, operating temperature, and mission-delivered energy**.

For analytics, the leading direction is:

```text
physics model + orbit/environment model + telemetry + uncertainty calibration
```

rather than either a purely empirical degradation curve or a purely machine-learning predictor.

## 1. Mature state of practice

### III-V multijunction remains the flight benchmark

NASA's 2026 Small Spacecraft State-of-the-Art report describes **3- to 5-junction III-V architectures** as current state of the art for space solar cells, with nominal efficiencies around 30% and high values around 34%. It explicitly emphasizes EOL performance at operating temperature and notes that mass, volume and deployment constraints can dominate cell efficiency in actual mission trades.

**Repository implication:** our reference model should start with an AM0-calibrated III-V array abstraction, even if the first numerical implementation uses pvlib-compatible single-diode machinery underneath.

### Array-level specific power matters as much as cell efficiency

The 2026 NASA report also frames specific power as a critical mission metric and surveys actual arrays across missions. The recent literature on flexible arrays reinforces the same direction: lightweight blankets, compact stowage and reliable deployment are increasingly part of the PV technology problem rather than separate structural concerns.

**Repository implication:** every technology model should eventually expose both electrical efficiency and array-level `W/kg`, `W/m²`, stowed volume and EOL energy delivery.

### Mission-aware expected-power modelling is established practice

NASA's SPACE model is used for Artemis/Orion/Gateway-related EPS analysis and accounts for mission events such as eclipse, constrained array pointing, maneuvers and radiation degradation. A 2025 open-access LEO study similarly combines illumination, thermal/electrical modelling and real spacecraft telemetry.

**Repository implication:** a credible expected-power model must be driven by time-varying mission geometry and EPS state, not by a single annual derate.

## 2. What changed recently

### Real flight data are pushing digital-twin methods forward

ESA's Cluster work is especially important for this repository. A 2025 SpaceOps paper describes a solar-array digital twin that combines a simplified physics model, Bayesian calibration, monitoring data and ML to forecast degraded power. Follow-on 2026 work extends the calibration problem with explicit model discrepancy reduction.

This is very close to the architecture we should target:

```text
nominal physics model
      +
telemetry calibration
      +
uncertainty / discrepancy model
      =
operational digital twin
```

### Perovskites crossed from promise to meaningful in-orbit evidence

Perovskites are no longer supported only by radiation-chamber results and short suborbital demonstrations. 2026 quasi-2D perovskite results from SSPD-1 reported real LEO performance over many eclipse cycles, with a champion rigid device retaining roughly 80% of initial efficiency over the reported in-orbit interval and flexible devices showing strong proton-radiation tolerance in companion tests. The Caltech repository provides an openly accessible manuscript and supporting material.

The remaining weakness is not simply absorber radiation tolerance. Flight and ISS/MISSE work points to **contacts, interfaces, ion migration, packaging and pre-flight environmental stability** as important limitations.

### Thin-film and ultrathin technologies have credible alternatives to III-V

Six-year flight results from the AlSat-1N thin-film experiment provide unusually long on-orbit evidence for lightweight CdTe devices. In 2026, ultra-thin silicon heterojunction cells also re-entered the discussion because low mass and radiation/annealing behavior can make specific power competitive even when absolute efficiency is below premium III-V devices.

### Analytics is moving toward physics-informed ML

A 2026 paper on TSURU telemetry develops a physics-informed thermal/electrical predictor using telemetry, energy-balance constraints and PV I-V constraints. NASA's 2025 EPS anomaly work likewise combines model-based and data-driven logic. This reinforces the central research position of this repository: **normalize telemetry with physics first; learn the residual second**.


## 3. Commercial SBSP moved from concept studies toward offtake signaling in 2026

A new development in late 2026 is the appearance of a **commercial power-purchase agreement for space-based solar power (SBSP)**. Virtus Solis Technologies and Brae Systems announced a 20-year agreement for an initial **100 MW of firm orbital solar power**, corresponding to **876,000 MWh/year**, for Brae's planned subsea datacenter infrastructure. The agreement includes an option to increase supply to **250 MW** within three years of initial commercial operation.

This should be treated as a **market/offtake signal rather than proof of technical readiness**. pv magazine explicitly notes that the infrastructure required to deliver the contracted power has not yet been deployed. Virtus Solis currently targets a public microwave power-transfer demonstration in March 2027 and a roughly 100 kW LEO pilot approximately two years after the announcement.

The proposed architecture differs from many classic GEO SBSP concepts. Virtus Solis describes highly elliptical **Molniya-orbit** arrays, 10 GHz microwave transmission, distributed modular satellites, and ground rectennas. The company states that a 100 MW system would comprise about **100,000 satellites**, each approximately 1.65 m and delivering about 1 kW to ground. These are company design claims and should not be treated as independently validated performance specifications.

The commercial announcement is notable because **AI/datacenter demand is a plausible first market for high-cost firm power**: datacenters can value power availability, long-term price certainty, siting flexibility, and potentially direct supply more highly than an undifferentiated grid customer. That does not by itself resolve the central SBSP challenges of launch cost, in-space assembly, wireless transfer efficiency, rectenna land use, regulatory approval, reliability, debris mitigation and lifecycle economics.

The gap between commercial ambition and established engineering evidence remains large. NASA's 2024 SBSP assessment concluded that the representative 2050 systems studied were still more expensive than terrestrial sustainable alternatives in its baseline cases, with lifecycle cost per unit energy estimated around **12–80× higher** unless major launch/manufacturing/capability improvements are achieved. ESA's SOLARIS work similarly treats multi-hundred-kW demonstrations, 100 MW pilots and later multi-GW systems as a staged development problem rather than a currently mature power technology.

**Repository implication:** space-PV analytics should include an SBSP system layer above the spacecraft-array layer:

```text
orbital PV generation
      ↓
DC collection / conversion
      ↓
RF conversion + phased-array efficiency
      ↓
beam geometry / pointing / atmosphere
      ↓
rectenna capture + RF-to-DC conversion
      ↓
ground delivery / datacenter load
      ↓
contracted availability and energy
```

This creates a new class of analytics: **delivered-energy performance**, not only solar-array performance.

## 4. Radiation modelling state of practice

The appropriate engineering chain is:

```text
orbit
  ↓
particle environment / spectrum
  ↓
shielding
  ↓
NIEL / displacement damage dose / equivalent fluence
  ↓
cell electrical degradation
```

IRENE/AE9/AP9/SPM is the modern near-Earth trapped-particle environment family and supports uncertainty-aware flux/fluence outputs. ESA exposes IRENE through its Network of Models. Recent literature continues to use NIEL/DDD-style approaches for semiconductor and solar-cell degradation.

A constant `x % per year` should therefore be treated only as a baseline or fitted summary statistic, not the physical state variable.

## 5. State-of-the-art analytics architecture

A strong 2026 implementation should separate these states:

| Layer | State |
|---|---|
| Mission | orbit, attitude, eclipse, operations timeline |
| Solar | Sun vector, distance, AM0 spectral irradiance |
| Thermal | cell/panel temperature and thermal history |
| Radiation | particle flux/fluence, shielding, NIEL/DDD |
| PV | junction/string/array I-V state |
| EPS | MPPT, shunt/direct-energy-transfer mode, battery/load state |
| Telemetry | measured V/I/T, attitude, EPS flags |
| Health | residual, degradation, fault state, RUL |
| Uncertainty | model parameters, measurement noise, discrepancy |

This is the target data model for `space-pv-analytics`.

## 6. What is *not* solved yet

The literature still leaves large gaps:

1. **Open, synchronized datasets are rare.** BIRDS is excellent but sparse compared with operational mission telemetry.
2. **Attitude observability is often missing.** Without panel-normal orientation, power residuals can confound pointing and degradation.
3. **Radiation attribution is uncertain.** It is difficult to separate radiation damage from UV, contamination, thermal aging, harness faults and EPS operational changes using telemetry alone.
4. **Multijunction spectral behavior is under-observed in flight.** Bus-level V/I telemetry rarely reveals individual junction current matching.
5. **Emerging-cell qualification is not standardized enough.** Perovskite stability results depend strongly on device stack, encapsulation and test protocol.
6. **Model discrepancy matters.** A calibrated physical model can still be systematically wrong; the ESA Cluster digital-twin work explicitly moves toward Bayesian uncertainty and discrepancy modelling.
7. **RUL should be probabilistic.** Single deterministic degradation curves are inadequate for mission decisions.

## 7. Recommended research thesis for this repository

The most defensible differentiator is:

> **An open, reproducible digital-twin lab for spacecraft PV that fuses orbital geometry, space environment, electrical/thermal PV models and real telemetry to estimate expected power, degradation and uncertainty.**

The first serious benchmark should not ask whether ML can detect a low-power panel. It should ask whether the system can explain a measured power observation as a function of:

```text
Sun → eclipse → AOI → AM0 → temperature → radiation → PV model → EPS state
```

and quantify the unexplained residual.

## Key sources

- NASA, **State-of-the-Art of Small Spacecraft Technology — Power**, 2026: https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/
- Drabczyk et al., **Space Photovoltaics: Materials, Device Concepts and Operational Challenges**, 2026, open access: https://www.mdpi.com/2079-9292/15/10/1978
- NASA GRC, **Solar Array Performance Modeling for NASA's Artemis Missions**, 2024: https://ntrs.nasa.gov/citations/20240010780
- Mohamed et al., **Developing a modelling environment of spacecraft solar array in low Earth orbit using real-time telemetry data**, 2025, open access: https://doi.org/10.1016/j.fraope.2025.100268
- Antonello et al., **A Digital Twin Solution for Solar Arrays Degradation Assessment and Power Production Prediction: Application to ESA Cluster Mission**, SpaceOps 2025, open paper: https://publications.spaceops.org/2025/download_by_id.php?id=0013
- Putz et al., **Beyond Earth: Resilience of Quasi-2D Perovskite Solar Cells in Space**, 2026, open repository copy: https://authors.library.caltech.edu/records/9brt4-5mb24
- AFRL, **IRENE-AE9/AP9/SPM**, public model/documentation: https://www.vdl.afrl.af.mil/programs/ae9ap9/factsheet.php
- BIRDS EPS dataset: https://github.com/BIRDSOpenSource/EPS_dataset
- pv magazine USA, **Virtus Solis signs PPA to supply space-based solar power to datacenter developer Brae Systems**, 2026-10-01: https://pv-magazine-usa.com/2026/10/01/virtus-solis-signs-ppa-to-supply-space-based-solar-power-to-datacenter-developer-brae-systems/
- Virtus Solis, **20-year PPA with Brae Systems**, company announcement: https://www.virtussolis.space/blog/virtus-solis-signs-landmark-20-year-ppa-with-brae-systems
- NASA OTPS, **Space-Based Solar Power**, 2024: https://ntrs.nasa.gov/citations/20230018600
- ESA, **SOLARIS / Space-Based Solar Power**, research activities: https://activities.esa.int/cluster/923
- Virtus Solis technology page (company-stated architecture): https://www.virtussolis.space/our-technology
