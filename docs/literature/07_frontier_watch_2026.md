# Frontier watch — late 2026 space-PV research

_Last reviewed: 2026-10-03_

This file tracks very recent or early-access work that is useful for architecture decisions but should not yet be treated as settled engineering practice.

## 1. Orbit-specific, spectrally resolved degradation

A 2026 early-access paper proposes a spectrally resolved degradation framework for perovskite solar cells in which orbit-specific exposure history and shielding alter the relative source terms driving degradation. This is important because it moves beyond coarse labels such as "LEO" or "GEO" and argues for preserving the **temporal and energy/spectral structure** of the environment.

**Repository consequence:** do not reduce the radiation environment too early. Retain energy bins and time/orbit context in Silver data so different degradation kernels can be applied later.

Reference: **A spectrally resolved degradation framework for perovskite solar cells under orbit-specific space stressors**, Solar Energy Materials and Solar Cells, 2026 early access / October issue: https://doi.org/10.1016/j.solmat.2026.114518

## 2. Topology-coupled damage modelling

A September 2026 Aerospace Science and Technology paper models how space-environment damage interacts with photovoltaic-array circuit configuration and changes array I-V behavior under fault/abnormal conditions.

This is a major analytics point: the same damaged-cell mechanism can produce different bus-level telemetry signatures depending on string/parallel topology, bypass/protection devices and operating point.

**Repository consequence:** `space-pv-pvmodel` needs an explicit electrical topology layer rather than only a lumped array derate.

Reference: **Impact of space environment damage effects on the electrical performance of spacecraft photovoltaic arrays with different configurations**, 2026: https://doi.org/10.1016/j.ast.2026.112139

## 3. Physics-informed telemetry prediction is becoming directly PV-specific

A 2026 early-access study using TSURU telemetry combines time-series learning with soft physical constraints for orbital thermal balance and photovoltaic I-V behavior. The goal is joint prediction of temperature, voltage and current under limited telemetry.

This matters because it is no longer generic "spacecraft anomaly ML"; the physics-informed model is directly targeted at body-mounted solar panels.

**Repository consequence:** after Case 1 is physically validated, build a PIML benchmark where the learned component is penalized for violating energy balance and PV constraints.

Reference: **Telemetry-driven physics-informed prediction for on-orbit thermal–electrical performance of solar panels in satellite power system**, Aerospace Science and Technology, 2026 early access / October issue: https://doi.org/10.1016/j.ast.2026.112268

## 4. Multi-physics degradation is moving from additive derates to coupled models

Recent work proposes photo-thermal-electrical degradation models in which radiation-induced material changes interact with optical absorption, thermal state and electrical output.

**Repository consequence:** our architecture should keep thermal, radiation and electrical models composable, but later allow iterative/coupled solving instead of assuming each derate is independent and multiplicative.

Reference: **A photo–thermal–electrical coupling degradation model for solar arrays under long-term space radiation**, Renewable Energy 267 (2026): https://doi.org/10.1016/j.renene.2026.125716

## 5. Perovskite evidence is shifting from material survival to full-device reliability

The frontier question has changed. Radiation tolerance of the absorber is increasingly well supported; current flight studies emphasize whether complete devices survive interfaces, contacts, ion migration, UV, thermal cycling, encapsulation and pre-flight handling.

This is clear when comparing:

- SSPD-1 / ALBA quasi-2D flight data: https://authors.library.caltech.edu/records/9brt4-5mb24
- MISSE full-device/film evaluation: https://doi.org/10.1002/smll.202508232
- 2026 thermal-shock testing: https://doi.org/10.1039/D5EE03704B

**Repository consequence:** do not model an emerging technology with one scalar `radiation_tolerance` score. Track separate degradation states for absorber, optical stack, contact/interface and packaging where data support it.

## 6. The likely next state of the art

The literature trajectory points toward a spacecraft PV digital twin with these properties:

```text
high-fidelity geometry
+ orbit-specific environment
+ technology-specific spectral/electrical model
+ coupled thermal state
+ array topology / EPS operating mode
+ telemetry assimilation
+ Bayesian uncertainty
+ learned discrepancy
```

The difficult part is no longer computing a nominal I-V curve. It is maintaining a calibrated, uncertainty-aware state estimate throughout the mission.

## Watch criteria

A paper should move from this file into the main state-of-art notes when at least one is true:

1. independent flight validation exists;
2. an open dataset enables reproduction;
3. the method is adopted by a mission/agency engineering workflow;
4. multiple groups demonstrate comparable results;
5. the method materially improves predictive uncertainty or operational decisions over simpler baselines.


## 6. Commercial frontier: space solar as firm power for AI/datacenters

On 30 September / 1 October 2026, Virtus Solis and Brae Systems announced a 20-year PPA for an initial 100 MW of continuous orbital solar power, with an option to scale to 250 MW. This is important to watch because it introduces a concrete **offtaker and load class** into SBSP discussions: AI/datacenter infrastructure.

Do not interpret the PPA as evidence that commercial SBSP is operational. The announced generation system, rectenna and customer infrastructure still require deployment. The near-term milestones are a public wireless-power demonstration in March 2027 and a proposed ~100 kW LEO pilot later.

### Why it matters scientifically

The commercialization problem changes the performance metric from array efficiency to **contracted delivered power**. A future SBSP digital twin therefore needs to model:

- orbital sunlight and array output;
- conversion from PV DC to RF;
- phased-array efficiency and beam steering;
- line-of-sight and constellation handover;
- atmospheric / propagation losses;
- rectenna capture and RF-to-DC efficiency;
- ground-grid or direct-load delivery;
- forced outages, maintenance and redundancy;
- PPA availability and annual-energy compliance.

For a 100 MW contract advertising 876,000 MWh/year, the numerical annual energy is exactly `100 MW × 8,760 h`, so the commercial promise is effectively a 100% nameplate-energy equivalent before considering contractual definitions, curtailment, exclusions and availability clauses. The repository should therefore distinguish **nameplate power**, **technical availability**, **delivered energy**, and **contractual availability**.

### Sources

- pv magazine USA (2026-10-01): https://pv-magazine-usa.com/2026/10/01/virtus-solis-signs-ppa-to-supply-space-based-solar-power-to-datacenter-developer-brae-systems/
- Virtus Solis company announcement (2026-09-30): https://www.virtussolis.space/blog/virtus-solis-signs-landmark-20-year-ppa-with-brae-systems
- NASA OTPS SBSP report: https://ntrs.nasa.gov/citations/20230018600
- ESA SOLARIS activities: https://activities.esa.int/cluster/923
