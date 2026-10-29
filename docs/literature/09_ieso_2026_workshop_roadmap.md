# 2026 IESO Space PV Workshop — roadmap and product implications

_Last reviewed: 2026-10-03_

## Source and evidence level

**Source:** *2026 IESO Space Photovoltaics Workshop: Findings and Participant Recommendations — Technical Priorities for Next-Generation Space Photovoltaics* (DOE Integrated Energy Systems Office workshop, June 2, 2026).

**Evidence level:** expert workshop synthesis. The report explicitly states that the targets and recommendations reflect workshop participants and are **not DOE commitments**. Treat quantitative targets as roadmap anchors, not regulatory requirements or guaranteed industry outcomes.

## Why this source matters to this repository

This workshop is especially valuable because it converts the space-PV problem into four things we can represent directly in software:

1. **normalized performance metrics**;
2. **mission-specific environment profiles**;
3. **combined-stressor reliability evidence**;
4. **shared flight / ground-test data with traceable qualification context**.

That aligns almost exactly with the intended architecture of this repository.

---

# 1. Quantitative targets to make first-class KPIs

The report synthesizes four cross-technology 2035 targets at the deployed-array level:

| KPI | Workshop target | Repository implication |
|---|---:|---|
| Array specific power | **>200 W/kg** | normalize power by deployed-array mass and preserve hardware boundary |
| Array areal power at EOL under AM0 | **>200 W/m²** | require area, AM0 condition, mission state and EOL definition |
| EOL retained power | **≥70% of BOL** for defined mission | model mission-specific degradation, not generic annual loss |
| Cost | **<$10/W** at defined boundary | add cost boundary / quantity / dollar-year metadata |

The workshop also discusses a 10-year LEO durability ambition and participant-proposed silicon targets, but the report itself flags some of those values as preliminary or insufficiently documented. They should therefore be stored as **scenario targets**, not hard-coded truth.

## Product feature: KPI target engine

Add a target engine capable of evaluating any mission / technology / array against configurable targets:

```text
specific_power_w_kg
areal_power_w_m2
retained_power_fraction
cost_usd_per_w
mission_years
```

Every KPI result must carry:

```text
hardware_boundary
illumination_reference
BOL_or_EOL
orbit_profile
mission_duration
production_volume
currency_year
source
```

This is essential because the workshop emphasizes that cell, CIC, panel/blanket and full-array metrics are **not directly comparable**.

---

# 2. Hardware-boundary ontology becomes mandatory

The report distinguishes four physical boundaries:

```text
CELL
  ↓
CIC — cell + interconnect + coverglass
  ↓
PANEL / BLANKET
  ↓
ARRAY / WING
```

This should become a repository-wide enum / ontology.

Suggested canonical enum:

```python
HardwareBoundary = Literal[
    "cell",
    "cic",
    "panel",
    "blanket",
    "array",
    "spacecraft_bus",
]
```

All efficiency, mass, area, cost, degradation and power records should state their boundary.

### Why

A bare-cell specific power in kW/kg is not comparable to an array-level W/kg value once substrate, wiring, hinges, deployment hardware, protection and harness are included.

---

# 3. Three technology families should remain parallel in the data model

The workshop recommends advancing three families in parallel rather than assuming one universal winner:

- **III–V**;
- **silicon**;
- **perovskite / thin film**.

The repo should therefore avoid a III–V-only schema.

## Suggested technology model

```text
TechnologyFamily
├── III_V
│   ├── 3J lattice matched
│   ├── IMM
│   └── future 4J/5J
├── SILICON
│   ├── heritage space Si
│   ├── terrestrial-derived ultrathin Si
│   └── constellation-scale Si
└── THIN_FILM
    ├── perovskite
    ├── tandem-perovskite
    └── other flexible thin films
```

The model should support technology-specific physics without changing the common mission / array / telemetry contracts.

---

# 4. Mission-specific environment profiles are a core product feature

One of the strongest workshop recommendations is to define environmental envelopes by mission class, including:

- LEO;
- MEO;
- GEO;
- cislunar;
- lunar surface;
- eventually deep-space mission classes.

Relevant stressors include:

```text
radiation
thermal cycling
vacuum
UV-rich AM0 illumination
atomic oxygen
micrometeoroids / debris
mechanical / launch loads
```

## Product feature: Mission Environment Profile

Add a reusable entity such as:

```yaml
mission_profile:
  orbit_class: LEO
  duration_years: 7
  altitude_km: 550
  inclination_deg: 53
  eclipse_cycles: derived
  temperature_min_c: -110
  temperature_max_c: 95
  radiation_model: IRENE_AE9_AP9
  radiation_percentile: 95
  atomic_oxygen: enabled
  uv_model: AM0
  micrometeoroid_model: null
```

The output should be a versioned exposure / stress profile that can drive both expected-power simulation and qualification scenarios.

---

# 5. Combined-stressor reliability is more important than isolated stressor tests

The workshop repeatedly emphasizes that future qualification should reproduce **combined mission-relevant stressors**, not only independent proton, electron, thermal or UV tests.

This creates a major feature direction for the lab:

## Product feature: Combined-Stressor Experiment Registry

Represent a test as:

```text
sample
technology
hardware boundary
pre-test characterization
stressor sequence / simultaneous stressors
radiation species + energy + fluence
thermal-cycle profile
illumination spectrum + intensity
vacuum
atomic oxygen
mechanical stress
measurement cadence
post-test characterization
recovery / annealing observations
```

A single experiment can then be linked to a mission environment profile and compared with flight data.

---

# 6. Degradation modeling needs recovery and metastability

The workshop goes beyond simple monotonic degradation. It specifically highlights predictive understanding of:

- radiation damage;
- recovery / annealing;
- combined-stressor effects;
- post-eclipse recovery;
- activation energies;
- metastability kinetics;
- low-temperature behavior down to roughly -110 °C for emerging thin-film/perovskite systems.

## Roadmap implication

The degradation API should not be only:

```python
P_EOL = P_BOL * (1 - degradation_rate * years)
```

Instead, support a stateful model:

```text
state(t+1) = f(
  radiation_dose,
  temperature_history,
  illumination_history,
  eclipse_history,
  annealing,
  technology_parameters,
)
```

This is particularly important for perovskites and other materials with reversible / metastable behavior.

---

# 7. Mechanical degradation belongs in the digital twin

The report recommends mechanical modeling of long-term degradation, including creep-level finite-element analysis, alongside radiation and thermal models.

## Repository implication

Add a future `mechanics` interface rather than hard-coding this into PV physics:

```text
space-pv-mechanics
├── thermal_cycle_fatigue
├── interconnect_stress
├── creep
├── deployment_structure
└── exported_fea_results
```

The initial implementation does not need a full FEA solver. It should support importing structural-model outputs and correlating them with electrical degradation / fault events.

---

# 8. Qualification evidence should be machine-readable

The report references heritage AIAA standards and argues for mission- and technology-specific qualification pathways that can evolve with flight evidence.

## Product feature: Qualification Matrix

For every technology / component / mission combination, store evidence such as:

```text
requirement
standard / protocol
stressor
threshold
sample count
pass / fail / partial
facility
test date
report link
raw-data link
flight correlation
confidence / maturity
```

The frontend can then expose a **qualification readiness matrix** rather than only performance charts.

Potential views:

- Technology × stressor heat map
- Technology × orbit suitability matrix
- Qualification evidence timeline
- Ground-test vs flight-evidence comparison

---

# 9. Shared flight + ground-test registry is directly aligned with this repo

The workshop recommends an open, anonymized registry of flight and ground-test data with quality control and governance.

This is one of the strongest validations of the repository direction.

## Product feature: Evidence Registry

Extend the existing connector / data-lake architecture with explicit provenance:

```text
EvidenceRecord
├── source_type: flight | ground_test | simulation | publication
├── source_org
├── mission / sample
├── technology
├── hardware_boundary
├── environment_profile
├── data_rights
├── export_control_flag
├── quality_level
├── raw_artifact
├── processed_artifact
├── model_version
└── citation
```

This lets the same analytics pipeline compare:

```text
ground prediction
      ↓
flight observation
      ↓
model discrepancy
      ↓
updated calibration
```

---

# 10. Model → test → flight → refine should be the lab operating loop

The workshop describes an iterative protocol-development loop that maps cleanly onto the repository:

```text
mission environment
        ↓
physics model
        ↓
predicted degradation
        ↓
combined-stressor ground test
        ↓
flight test / operational telemetry
        ↓
compare predictions and observations
        ↓
calibrate / update model
        └───────────────↺
```

This should become the core conceptual workflow of `labs/`.

Each serious lab should identify which part of the loop it covers and what evidence closes the loop.

---

# 11. Technology-to-mission capability matrix

The workshop recommends technoeconomic analyses and a capability matrix matching emerging PV technologies to mission demands and stressors.

## Product feature: Mission / Technology Trade Space

For each technology and mission profile, compute:

```text
BOL W
EOL W
Wh delivered over mission
W/kg
Wh/kg
W/m²
cost/W
cost/mission-Wh
radiation margin
thermal margin
qualification maturity
manufacturing maturity
supply-chain risk
```

This turns the repository into a decision-support tool rather than only a monitoring platform.

---

# 12. Supply-chain context is secondary but useful metadata

The report highlights concentrated Ga/Ge supply chains, coverglass dependencies, manufacturing capacity, substrate reuse, high-throughput growth and terrestrial-Si leverage.

This is not the primary scope of PV performance analytics, but it can be represented as optional technology metadata:

```text
critical_materials
supplier_count
country_concentration
substrate_reuse_count
manufacturing_capacity_mw_year
manufacturing_process
TRL / MRL
```

This becomes valuable in technology-selection and technoeconomic studies.

---

# 13. Feature priorities derived from the workshop

## Immediate repository priorities

1. Add `HardwareBoundary` and mandatory metric-context metadata.
2. Add `MissionEnvironmentProfile` and orbit-class templates.
3. Add normalized BOL/EOL KPI functions.
4. Add technology registry for III–V / Si / thin-film-perovskite.
5. Add combined-stressor experiment schema.
6. Add qualification / evidence registry schema.
7. Add ground-test ↔ flight-data cross-linking.
8. Add target dashboard using the workshop metrics.
9. Add mission-technology capability matrix.
10. Add recovery / annealing state to degradation interfaces.

## Medium-term

1. automatic environment-profile generation from orbit;
2. coupled radiation + thermal + illumination degradation;
3. qualification-gap analytics;
4. recurring flight-test dataset ingestion;
5. mechanical / FEA result adapter;
6. Bayesian calibration using paired ground + flight evidence.

## Long-term

1. predictive mission-life digital twin;
2. EOL retained-power distribution with uncertainty;
3. cross-technology mission optimizer;
4. community-ready open evidence registry;
5. qualification protocol recommendation engine.

---

# 14. Frontend features suggested by this workshop

The scientific frontend should eventually contain these pages:

```text
Mission Builder
Environment Profile
Technology Explorer
Array Performance
BOL → EOL Degradation
Qualification Matrix
Combined-Stressor Tests
Flight Evidence
Ground vs Flight Comparison
Technology × Mission Trade Space
2035 Target Dashboard
```

For a selected mission / technology, the user should be able to see:

```text
              BOL                                  EOL
               │                                    │
               ├──────── degradation trajectory ────┤
               │                                    │
 specific W/kg                             retained power %
 areal W/m²                                areal W/m²
 cost/W                                    mission Wh/kg
               │                                    │
               └──── evidence + uncertainty ────────┘
```

---

# 15. Repository design principle reinforced by the workshop

The strongest takeaway is that **space PV performance cannot be represented by cell efficiency alone**.

The useful object of analysis is:

```text
technology
+ hardware boundary
+ mission environment
+ spacecraft / array architecture
+ manufacturing / qualification state
+ stressor history
+ telemetry
+ ground-test evidence
──────────────────────────────────────
mission-specific BOL → EOL power and energy
```

That should remain the organizing principle of this repository.
