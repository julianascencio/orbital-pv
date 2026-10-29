# Space-based solar power: market, datacenter and system-analytics context

_Last reviewed: 2026-10-03_

## Why this belongs in a PV performance repository

Space-based solar power (SBSP) extends the performance problem from **how much electrical power a spacecraft solar array produces** to **how much useful energy is delivered to a terrestrial or in-space customer**. The same orbit, Sun, radiation, thermal and PV models remain necessary, but they become only the first part of a much longer energy chain.

This topic became more commercially relevant in late 2026 when Virtus Solis Technologies and Brae Systems announced a long-term power purchase agreement (PPA) tied to planned datacenter infrastructure.

## October 2026 Virtus Solis / Brae Systems announcement

### Documented commercial terms

Independent coverage and the companies' announcement describe:

- **20-year PPA**;
- **initial contracted supply: 100 MW**;
- **annual energy: 876,000 MWh/year**;
- customer: Brae Systems' planned subsea / underwater datacenter infrastructure;
- option to expand supply to **250 MW** within three years of initial commercial operations;
- first receiving station planned in Illinois alongside a pilot datacenter.

The `876,000 MWh/year` figure equals `100 MW × 8,760 h/year`, so the stated annual energy is equivalent to continuous delivery at the full 100 MW nameplate. The actual PPA's legal definitions of availability, outages, commissioning conditions, force majeure, curtailment and performance guarantees are not public in the cited sources.

### Technology status

The infrastructure is **not yet operating**. pv magazine states that both sides still need to deploy the infrastructure required to realize the agreement. Reported milestones include:

- public microwave power-transfer demonstration: **March 2027**;
- proposed orbital pilot: roughly **100 kW in LEO**, targeted about 24 months after the October 2026 report.

Therefore this belongs in the repository as a **commercial frontier / technology watch**, not as evidence that utility-scale SBSP has reached operational maturity.

## Proposed Virtus Solis architecture

Virtus Solis describes a distributed architecture with:

- highly elliptical **Molniya orbits**;
- approximately 12-hour orbital periods and long high-latitude dwell times;
- multiple arrays providing handover / continuous receiver visibility;
- modular satellites;
- solar-to-RF conversion and **10 GHz microwave** transmission;
- ground rectennas converting RF back to electricity;
- potential use of lightweight/perovskite PV technology.

The company's technology page states that a 100 MW system could use about **100,000 satellites**, with each ~1.65 m satellite delivering approximately 1 kW to ground. These are **company-stated design parameters** and should be stored in the project as assumptions/proposals, not measured operational performance.

A relevant peer-reviewed orbit/attitude study has found Molniya orbits worthy of further investigation for planar-array SBSP beaming; that work received funding from Virtus Solis, which should be recorded in provenance when it is used.

## Why datacenters are an interesting first offtaker

The datacenter use case is technically and economically interesting because AI infrastructure values:

- continuous high power;
- predictable long-term energy pricing;
- fast capacity additions where grid interconnection is constrained;
- geographic flexibility;
- high willingness to pay for reliable power;
- potential co-design of generation, direct supply, cooling and compute scheduling.

That creates a very different optimization target from commodity grid energy. An SBSP system may be commercially useful to a constrained datacenter even before it is the lowest-LCOE bulk generation technology.

This is a hypothesis to test, not a conclusion.

## Reality check against NASA and ESA assessments

NASA's 2024 Office of Technology, Policy, and Strategy assessment found substantial remaining capability gaps in:

- low-cost launch;
- in-space assembly and maintenance;
- autonomous operations;
- large structures;
- wireless power transmission;
- lifecycle manufacturing and logistics.

For the representative 2 GW 2050 systems studied, NASA reported baseline lifecycle electricity costs far above terrestrial sustainable alternatives—roughly **12–80 times higher** in the modeled baseline—while noting that favorable launch/manufacturing/capability improvements could materially change competitiveness.

ESA's SOLARIS work similarly treats SBSP as a staged R&D and demonstration challenge. Public ESA roadmap material has discussed a progression from ground demonstrations to hundreds-of-kW space demonstrators, then ~100 MW pilots, before multi-GW operational systems.

The Virtus Solis PPA is therefore best interpreted as evidence that **commercial demand may form before all technology risks are retired**. It does not invalidate NASA/ESA's technology-readiness or economics concerns.

## End-to-end performance model for this repository

The SBSP energy chain should be modeled explicitly:

```text
Sun / spectrum / orbital geometry
          ↓
space PV array P_DC
          ↓  η_collection
DC power aggregation / distribution
          ↓  η_DC-RF
RF generation
          ↓
phased-array beamforming
          ↓  η_beam + pointing + sidelobes
space-to-ground propagation
          ↓  η_propagation
rectenna capture
          ↓  η_RF-DC
ground conditioning / transmission
          ↓  η_ground
datacenter bus / grid meter
          ↓
contracted delivered power and energy
```

A convenient first-order relation is:

```text
P_delivered = P_PV
              × η_collection
              × η_DC-RF
              × η_beam
              × η_propagation
              × η_rectenna
              × η_ground
              × availability_state
```

Each efficiency should be a time-varying state with provenance and uncertainty rather than one hard-coded scalar.

## New data model concepts

Add system objects beyond `satellite` and `pv_array`:

```text
sbsp_system
├── constellation
│   ├── spacecraft
│   ├── orbital_plane / orbit_family
│   └── handover_policy
├── pv_generation_unit
├── rf_transmitter
├── beam
├── rectenna_site
├── power_delivery_point
├── offtaker
├── load_site
└── ppa_contract
```

Useful time-series metrics:

```text
P_pv_dc
P_rf_tx
P_rf_incident
P_rectenna_dc
P_metered
η_dc_rf
η_beam
η_rectenna
beam_pointing_error
receiver_visibility
constellation_availability
energy_delivered_mwh
contracted_power_mw
PPA_compliance_ratio
```

## Analytics / lab opportunities

### SBSP-01 — Molniya constellation availability

Simulate 1–N arrays and quantify receiver line-of-sight, handovers, eclipse and delivered-power continuity for candidate rectenna locations.

### SBSP-02 — end-to-end efficiency waterfall

Build an energy waterfall from AM0 solar input to customer meter and quantify the sensitivity of delivered LCOE to each conversion stage.

### SBSP-03 — 100 MW PPA compliance simulation

Model whether a candidate constellation can deliver 100 MW firm power and 876,000 MWh/year under outages, degradation, maintenance and beam handover constraints.

### SBSP-04 — datacenter co-optimization

Couple orbital power availability to a datacenter load model:

```text
GPU workload scheduling
+ cooling demand
+ battery / UPS
+ terrestrial grid backup
+ SBSP power
```

Optimize cost, carbon, uptime and compute throughput.

### SBSP-05 — rectenna GIS

Use PostGIS/Cesium to model:

- receiver location and land footprint;
- satellite visibility windows;
- beam incidence geometry;
- exclusion / safety areas;
- grid and datacenter proximity;
- weather/atmospheric context where relevant;
- multi-receiver power allocation.

### SBSP-06 — technology-risk Monte Carlo

Propagate uncertainty in launch cost, PV specific power, RF efficiency, spacecraft failure rate, replacement cadence and rectenna cost to delivered-energy cost and availability.

## Evidence classification for project use

| Item | Evidence class | Repository treatment |
|---|---|---|
| Signed/announced Virtus Solis–Brae PPA | Commercial announcement / independent reporting | Market signal |
| 100 MW / 876,000 MWh/year | Announced contract term | Scenario input, not operational result |
| 250 MW option | Announced option | Upside scenario |
| Molniya / 10 GHz / modular satellites | Company architecture | Proposed design assumption |
| 100,000 satellites / 100 MW | Company architecture | Sensitivity input only |
| March 2027 demo | Company milestone | Future watch item |
| ~100 kW LEO pilot | Company milestone | Future watch item |
| NASA cost/TRL findings | Government system study | Independent baseline / reality check |
| ESA SOLARIS roadmap | Government R&D program | Independent technology roadmap |

## Sources

- pv magazine USA, 2026-10-01, **Virtus Solis signs PPA to supply space-based solar power to datacenter developer Brae Systems**: https://pv-magazine-usa.com/2026/10/01/virtus-solis-signs-ppa-to-supply-space-based-solar-power-to-datacenter-developer-brae-systems/
- Virtus Solis, 2026-09-30, **Virtus Solis Signs Landmark 20-Year PPA with Brae Systems**: https://www.virtussolis.space/blog/virtus-solis-signs-landmark-20-year-ppa-with-brae-systems
- Virtus Solis, **Our Technology**: https://www.virtussolis.space/our-technology
- NASA OTPS, 2024, **Space-Based Solar Power**: https://ntrs.nasa.gov/citations/20230018600
- NASA ASCEND summary, 2024: https://ntrs.nasa.gov/citations/20240008752
- ESA, **Solar Power Satellites and WPT / SOLARIS activities**: https://activities.esa.int/cluster/923
- ESA, **ESA accelerates the race towards clean energy from space**: https://www.esa.int/Space_in_Member_States/United_Kingdom/ESA_accelerates_the_race_towards_clean_energy_from_space
- **Simultaneous orbit and attitude optimization of planar arrays for space-based solar power beaming**, Acta Astronautica, 2024: https://www.sciencedirect.com/science/article/pii/S0094576524001802
- **Space solar power generation: A viable system proposal and technoeconomic analysis**, 2025: https://www.sciencedirect.com/science/article/pii/S2542435125001096
