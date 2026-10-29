# Product feature roadmap — Space PV Analytics

_Last reviewed: 2026-10-03_

This document converts the technical literature, the 2026 IESO Space PV workshop, and the current repository architecture into a buildable product roadmap.

## Product thesis

The product should answer a decision-quality question:

> Given a PV technology, hardware boundary and mission environment, what power and energy will actually be available through mission life, why will it change, and how strong is the evidence?

That requires more than orbit visualization or telemetry charts. The product must connect mission conditions, physical models, ground qualification evidence and flight telemetry.

## Epic A — Mission Builder

**Goal:** define the conditions under which performance must be evaluated.

Features:
- mission name, orbit class and duration;
- propagated orbit from OMM/TLE/SPICE;
- LEO/MEO/GEO/cislunar/lunar templates;
- eclipse statistics;
- temperature envelope;
- radiation environment selection + percentile;
- AM0 / solar-distance profile;
- atomic-oxygen / UV / micrometeoroid flags;
- versioned `MissionEnvironmentProfile` export.

Frontend:
- dynamic Cesium orbit;
- timeline + eclipse bands;
- stressor summary cards;
- editable environment assumptions.

Backend:
- Postgres mission metadata;
- Parquet/DuckDB high-resolution environmental time series;
- Celery generation jobs.

## Epic B — Technology & Array Registry

**Goal:** normalize apples-to-apples comparison.

Features:
- III-V, Si, perovskite/thin-film families;
- cell / CIC / panel / blanket / array boundaries;
- BOL electrical parameters;
- mass and area;
- topology and protection components;
- coverglass / encapsulation / substrate;
- manufacturing and qualification metadata;
- source/citation provenance.

Critical rule: every performance number declares its **hardware boundary**.

## Epic C — BOL → EOL Performance Twin

**Goal:** simulate expected power across mission life.

Model hierarchy:
- L0 geometry-only;
- L1 + temperature;
- L2 + I–V / string topology;
- L3 + radiation degradation;
- L4 + coupled thermal / radiation / illumination history;
- L5 + telemetry-calibrated digital twin.

Outputs:
- instantaneous expected power;
- orbit/day energy;
- retained power fraction;
- W/kg and W/m²;
- EOL confidence interval;
- power-margin probability.

## Epic D — Combined-Stressor Lab

**Goal:** represent qualification evidence in the same data model as flight data.

Features:
- sample registry;
- radiation species / energy / fluence;
- temperature-cycle profiles;
- UV / AM0 exposure;
- vacuum;
- atomic oxygen;
- mechanical stress;
- simultaneous vs sequential stressors;
- before/during/after measurements;
- recovery / annealing / metastability observations.

Frontend:
- experiment timeline;
- stressor overlay;
- before/after I–V and power curves;
- comparison to mission environment envelope.

## Epic E — Evidence & Qualification Matrix

**Goal:** turn literature, tests and flights into machine-readable readiness evidence.

Features:
- requirement / standard / protocol;
- test evidence;
- sample count;
- pass/fail/partial;
- facility and date;
- raw data / report link;
- flight correlation;
- confidence / maturity;
- export-control / data-rights flags.

Views:
- technology × stressor matrix;
- technology × orbit suitability;
- missing-evidence/gap analysis;
- qualification timeline.

## Epic F — Flight Evidence Explorer

**Goal:** validate physics with operational data.

Sources:
- BIRDS;
- SatNOGS;
- NASA / ESA mission datasets;
- future contributed datasets.

Features:
- synchronized orbit, attitude, Sun, eclipse and EPS telemetry;
- expected vs measured power;
- residuals;
- panel/string health;
- change points;
- radiation-event context;
- ground-test linkage.

## Epic G — Model → Ground → Flight → Refine

**Goal:** make calibration and evidence accumulation the core research loop.

Workflow:

```text
Mission profile
    ↓
Physics prediction
    ↓
Ground test
    ↓
Flight observation
    ↓
Residual / discrepancy
    ↓
Parameter update
    ↓
Updated EOL forecast
```

Features:
- model versioning;
- calibration datasets;
- Bayesian / ensemble parameter posterior;
- explicit model-discrepancy term;
- reproducible artifact manifest.

## Epic H — 2035 Target Dashboard

Workshop-derived scenario targets:
- >200 W/kg array specific power;
- >200 W/m² EOL array areal power under AM0;
- >=70% BOL power retained for defined mission;
- < $10/W at a defined array boundary.

The dashboard should show:
- target;
- modeled value;
- measured evidence;
- confidence / maturity;
- hardware boundary;
- mission profile;
- source.

Do not present workshop targets as DOE commitments.

## Epic I — Mission × Technology Trade Space

**Goal:** select technologies based on mission value rather than cell efficiency.

KPIs:
- BOL W;
- EOL W;
- mission Wh;
- W/kg;
- Wh/kg;
- W/m²;
- cost/W;
- cost/mission-Wh;
- radiation margin;
- thermal margin;
- qualification maturity;
- manufacturing maturity;
- supply-chain risk.

Frontend:
- sortable comparison table;
- Pareto frontier;
- mission suitability matrix;
- uncertainty bars.

## Epic J — Recovery-aware degradation

The degradation layer must support technologies that do not degrade monotonically.

State variables may depend on:
- cumulative radiation dose;
- temperature history;
- illumination / darkness history;
- eclipse recovery;
- annealing;
- metastability;
- active hardening or recovery treatments.

This is especially relevant for emerging thin-film/perovskite technologies.

## Epic K — Mechanical reliability adapter

Future interface for:
- thermal-cycle fatigue;
- interconnect fatigue;
- creep;
- deployment structure;
- imported FEA result fields;
- correlation with electrical degradation or faults.

The repository should ingest FEA outputs before attempting to become an FEA solver itself.

## Delivery order

### Now — scientific normalization
1. hardware-boundary enum + metadata validation;
2. mission-environment profile schema;
3. technology registry;
4. workshop KPI engine;
5. BOL/EOL context fields;
6. frontend target cards.

### Next — evidence integration
1. combined-stressor experiment schema;
2. qualification-evidence registry;
3. BIRDS flight benchmark;
4. SatNOGS EPS+ADCS benchmark;
5. environment-profile generator;
6. ground ↔ flight comparison page.

### Later — predictive decision support
1. coupled degradation model;
2. recovery / annealing state;
3. Bayesian calibration;
4. qualification-gap engine;
5. technology × mission optimizer;
6. mechanical reliability adapter;
7. open evidence registry.

## Definition of decision-grade

A metric or prediction is decision-grade only if the system can answer:

```text
technology?
hardware boundary?
BOL / EOL?
illumination reference?
mission / orbit?
mission duration?
stressor history?
model version?
evidence source?
uncertainty?
```

Anything missing this context should be visibly labeled exploratory or incomplete.
