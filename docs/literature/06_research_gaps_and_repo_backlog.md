# Research gaps translated into repository backlog

_Last reviewed: 2026-10-03_

This document converts the current literature into concrete work for the repository.

## Priority 0 — establish a scientifically traceable reference chain

### P0.1 Canonical time and coordinate-frame contract

Implement explicit representations for:

- UTC/TAI/TT;
- TEME, GCRS/ECI, ITRS/ECEF;
- spacecraft body frame;
- panel frame;
- Sun vector source and ephemeris version.

**Why:** geometry errors can masquerade as PV-model error.

### P0.2 AM0 spectral resource

Add a versioned solar-spectrum dataset and metadata. Keep broadband `solar_constant / r_AU²` as the L0 model but build a spectral interface for multijunction work.

### P0.3 Deterministic eclipse validation

Benchmark eclipse/penumbra geometry against Skyfield/SPICE examples and selected mission events.

## Priority 1 — first end-to-end flight benchmark

### P1.1 BIRDS + reconstructed orbit

Create a reproducible dataset containing:

```text
BIRDS panel V/I/T
+ historical orbit elements
+ propagated position
+ Sun vector
+ eclipse state
+ solar distance
```

Then quantify how much of panel-power variation is explainable before attitude information.

### P1.2 Attitude-aware public satellite

Use SatNOGS to identify at least one satellite exposing both:

```text
EPS telemetry + Sun vector/quaternion
```

This becomes the first full physics-normalized flight benchmark.

### P1.3 Expected-power hierarchy

Implement and compare:

- L0 geometric model;
- L1 temperature correction;
- L2 single-diode/string model;
- L3 radiation-aware model.

Report incremental error reduction.

## Priority 2 — radiation-aware degradation

### P2.1 IRENE integration adapter

Add a reproducible interface to IRENE/AE9/AP9 output, including environment version and percentile.

### P2.2 DDD / equivalent-fluence package

Create technology-specific response interfaces rather than embedding degradation directly in the orbit model.

### P2.3 Uncertainty propagation

Monte Carlo from environment percentile + degradation parameters to EOL power distribution.

## Priority 3 — digital-twin calibration

Inspired by the ESA Cluster literature:

### P3.1 Parameter estimation

Calibrate uncertain PV/thermal/degradation parameters from telemetry.

### P3.2 Bayesian posterior

Return parameter distributions and predictive intervals, not only best-fit values.

### P3.3 Model discrepancy

Add an explicit discrepancy term (e.g. Gaussian process or structured residual model) so physical parameters do not absorb all missing physics.

## Priority 4 — fault diagnosis

### P4.1 Physics residual baseline

Robust residual z-score + change-point detection.

### P4.2 Electrical topology faults

Simulate:

- string open circuit;
- string short;
- bypass diode activation/failure;
- partial panel loss;
- harness resistance increase;
- MPPT/regulator mode shift.

Train fault classifiers only after these signatures are physically understood.

### P4.3 Radiation vs discrete-fault attribution

Compare cumulative exposure indicators with abrupt residual change points.

## Priority 5 — technology comparison

Build mission-level comparison of:

- III-V 3J/4J/IMM;
- CdTe thin film;
- ultrathin silicon;
- perovskite;
- future tandems.

Optimize for:

```text
EOL Wh delivered / kg launched
```

rather than BOL cell efficiency.

## Priority 6 — frontend scientific visualization

The dynamic Cesium view should expose model state, not just a moving satellite:

- sunlit / penumbra / eclipse coloring;
- Sun vector and panel-normal vector;
- AOI;
- instantaneous expected vs measured power;
- radiation-belt/environment overlay;
- selected residual/degradation state;
- time scrubber synchronized with telemetry charts.

## Priority 7 — SBSP delivered-energy analytics

The Virtus Solis / Brae Systems 2026 PPA creates a useful commercial research case: evaluate whether a proposed orbital generation system can meet a contracted **ground-delivered power and availability requirement**, not only whether its solar arrays generate power.

### P7.1 End-to-end SBSP efficiency chain

Model:

```text
PV DC
→ power conditioning
→ DC/RF
→ phased-array transmitter
→ beam propagation
→ rectenna capture
→ RF/DC
→ ground delivery
```

Track instantaneous efficiency, annual delivered energy, thermal/reliability losses and uncertainty at every stage.

### P7.2 Molniya constellation availability

Implement HEO/Molniya propagation, receiver line-of-sight, beam handover and constellation scheduling. Calculate the number of active transmitters required to maintain a 100 MW-class firm-delivery target.

### P7.3 PPA compliance simulator

Given contracted MW, annual MWh and availability clauses, calculate:

- delivered MWh;
- outage hours;
- availability;
- energy shortfall;
- replacement / redundancy requirements;
- confidence interval of contract compliance.

### P7.4 Datacenter coupling

Add load-side models for:

- IT load;
- cooling load;
- UPS/BESS;
- terrestrial grid connection;
- compute workload flexibility.

Optimize cost, uptime, emissions and compute throughput.

### P7.5 SBSP techno-economic uncertainty

Monte Carlo over launch cost, specific power, RF conversion, beam efficiency, satellite failure rate, servicing/replacement, rectenna cost and financing. Compare company scenarios with NASA/ESA reference ranges.

### P7.6 GIS / dynamic visualization

Display:

- Molniya/GEO/LEO constellations;
- receiver visibility cones;
- active beam paths;
- rectenna footprints;
- handovers;
- delivered-power heat maps;
- datacenter and grid nodes.

## Priority 8 — qualification, evidence and mission-specific technology selection

The 2026 IESO Space PV workshop reinforces that the repository should connect performance analytics with mission-specific qualification and evidence.

### P8.1 Hardware-boundary ontology

Add canonical boundaries for cell, CIC, panel/blanket, array and spacecraft-bus metrics. Require the boundary on power, efficiency, mass, area, specific-power and cost records.

### P8.2 Mission Environment Profile

Create versioned environment templates for LEO, MEO, GEO, cislunar and lunar-surface missions, populated from orbit and environment models where possible.

### P8.3 Combined-stressor experiment registry

Model radiation, thermal, UV, vacuum, atomic oxygen, mechanical and other stressors as ordered or simultaneous test exposures linked to sample-level measurements.

### P8.4 Qualification evidence matrix

Represent requirements, test protocols, standards, sample counts, pass/fail evidence and flight correlation in a machine-readable schema.

### P8.5 Model → ground → flight → refine loop

Create a standard lab workflow that compares model predictions with matched ground-test and flight evidence and stores model discrepancy/calibration updates.

### P8.6 Mission / technology capability matrix

Compare III-V, silicon and thin-film/perovskite technologies by mission-specific BOL/EOL power, Wh/kg, W/m², cost, qualification maturity and uncertainty.

### P8.7 Recovery / annealing-aware degradation

Extend the degradation API to support reversible or metastable behavior driven by radiation, temperature, illumination and eclipse history.
