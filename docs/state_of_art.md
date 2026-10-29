# State of the art — space photovoltaic performance analytics

> **2026 literature library:** a substantially expanded and source-tagged review is available under [`docs/literature/`](literature/README.md), starting with [`00_current_state_of_art_2026.md`](literature/00_current_state_of_art_2026.md).
_Last reviewed: 2026-09-08_

## 1. Executive view

Space PV performance analytics is moving from static BOL/EOL sizing toward **mission-aware digital performance models** that combine orbital geometry, thermal behavior, radiation degradation and operational telemetry. NASA's SPACE model is used for mission power analysis and has been applied to Orion and Gateway/PPE. ESA-focused work published in 2025 demonstrated a physics-based degradation model calibrated against Cluster flight data. At the same time, public CubeSat telemetry and spacecraft anomaly datasets are making data-driven diagnostics reproducible.

For this lab, the highest-value research direction is therefore **hybrid model + data analytics** rather than a purely ML approach or a purely cell-physics simulator.

## 2. Current cell and array technology

### Flight-proven baseline

- III-V multi-junction cells remain the dominant high-performance space technology because of efficiency and radiation tolerance. NASA's 2026 Small Spacecraft State of the Art page describes 3- to 5-junction III-V architectures as current state of the art, with nominal efficiencies around 30% and high values around 34%.
- Current deployable arrays increasingly emphasize specific power, packaging and reliability. Roll-Out Solar Array (ROSA) technology is operational on ISS and used in deep-space/Gateway-related architectures.
- Mission-relevant performance is **EOL power at operating temperature**, not laboratory efficiency alone.

### Emerging technologies

- Inverted metamorphic and higher-junction III-V devices seek higher efficiency and specific power.
- Perovskites and perovskite tandems are attractive for mass-specific power and manufacturing, but contacts/interfaces, pre-flight stability, vacuum/UV/thermal cycling and mission qualification remain active problems.
- 2026 orbital results on quasi-2D perovskites reported substantial retained performance through many LEO eclipse cycles, strengthening the case for flight-oriented analytics rather than only ground-test extrapolation.
- Flexible/thin-film and concentrator concepts matter because array-level W/kg and stowed W/m³ can dominate mission value.

## 3. Performance drivers that must be modeled

A useful expected-power model should treat these factors independently where possible:

1. **Solar distance / AM0 irradiance:** approximately inverse-square with Sun-spacecraft distance, with spectral effects important for multijunction devices.
2. **Sun incidence / attitude:** cosine response is only the first approximation; array articulation and off-pointing constraints matter.
3. **Eclipse and occultation:** binary/partial illumination windows dominate LEO power availability.
4. **Cell/junction temperature:** affects current, voltage and maximum power; LILT and HIHT regimes can need dedicated models.
5. **Radiation:** electrons and protons create displacement damage; trapped-belt exposure depends strongly on orbit and shielding.
6. **UV, atomic oxygen, contamination and coverglass darkening:** particularly relevant in LEO and long missions.
7. **Electrical topology:** string failures, bypass/protection diodes, reverse-bias events, MPPT/BCR behavior, harness losses.
8. **Mechanical / operational state:** deployment, shadowing, maneuvers, plume events, micrometeoroids and EPS load-control mode.

## 4. Radiation degradation modeling

The classic engineering workflow uses equivalent fluence and/or **displacement damage dose (DDD)**. Non-ionizing energy loss (NIEL) provides an energy-dependent bridge between proton/electron spectra and device damage. Modern radiation-environment tools include AE9/AP9 for near-Earth trapped electron/proton populations; ESA's Network of Models exposes NIEL workflows and SPENVIS-backed models.

The analytics architecture should therefore keep three distinct layers:

```text
orbit / environment -> particle spectrum / fluence -> shielding/NIEL/DDD -> PV degradation law
```

Do not collapse them into a single empirical "degradation %/year" constant except as a crude baseline.

## 5. Data-driven monitoring

Public BIRDS CubeSat EPS telemetry is unusually valuable because it includes panel voltage, current and temperature from four 1U spacecraft, with known panel failures on two satellites. Published work has already used these data for ML anomaly detection.

For research quality, data-driven models should operate on **physics-normalized residuals** where possible:

```text
residual = measured_power - expected_power(geometry, temperature, radiation, EPS state)
```

This makes anomalies more explainable and transfer across missions more plausible. NASA's 2025 work on spacecraft EPS monitoring likewise points toward hybrid model/data-driven fault detection.

## 6. Recommended KPI hierarchy

### Instantaneous / orbit-level
- `P_meas = V * I`
- expected available array power
- normalized power ratio `P_meas / P_expected`
- residual power and robust residual score
- energy per sunlit orbit
- eclipse recovery behavior
- temperature coefficient / thermal hysteresis

### Degradation / health
- normalized BOL-to-current power retention
- degradation slope (%/day, %/year, %/equivalent fluence)
- DDD / equivalent-fluence response
- panel-to-panel imbalance
- string availability / inferred failed-string count
- change-point dates and persistent residual loss

### Mission / business-system metrics
- EOL power margin
- Wh/orbit and Wh/day available to payload
- specific power (W/kg) and specific energy contribution
- power shortfall probability under mission scenarios
- useful-life / remaining-power forecast with confidence bounds

## 7. Open data and software stack

### Data
- **BIRDS EPS dataset:** real panel/battery telemetry from multiple CubeSats; first lab dataset.
- **OPS-SAT-AD:** ESA OPS-SAT telemetry benchmark for generic spacecraft anomaly detection; useful later for cross-subsystem methods.
- **NASA/ESA mission products and SPICE kernels:** geometry and attitude for supported missions.
- **OMNI / space-weather data:** useful context for storms and radiation environment.

### Software
- **SpiceyPy / SPICE:** authoritative spacecraft/planetary geometry and mission kernels.
- **SpacePy:** CDF, coordinates, OMNI and AE9/AP9-output handling.
- **AE9/AP9/IRENE:** trapped radiation environment specification.
- **ESA SPENVIS / Network of Models:** environment/effects workflows including NIEL.

## 8. Standards / qualification context

- ECSS-E-ST-20-08C Rev.2 (2023) is the active ECSS standard for photovoltaic assemblies and components.
- ECSS-E-ST-10-12C covers methods for radiation received/effects and design margins.
- AIAA S-122 is an active NASA-endorsed electrical power-system standard for unmanned spacecraft.

The lab is not a qualification tool. It should preserve traceability to standards and distinguish exploratory models from validated engineering models.

## 9. Research gaps worth targeting

1. Transferable expected-power modeling across spacecraft with sparse attitude data.
2. Decomposing observed long-term power loss into radiation, thermal/UV aging and discrete electrical faults.
3. Uncertainty-aware EOL forecasting rather than a single deterministic degradation curve.
4. Fast surrogate models for radiation-aware mission optimization.
5. Fault signatures that can distinguish failed strings, MPPT/BCR behavior, attitude effects and thermal effects.
6. Technology-comparison models that optimize **mission delivered energy per mass**, not cell efficiency only.
7. Onboard-capable diagnostics with interpretable, low-compute models.

## 10. Sources

- NASA Small Spacecraft State of the Art — Power: https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/
- NASA Artemis solar array performance modeling: https://ntrs.nasa.gov/citations/20240010780
- NASA hybrid model/data-driven EPS anomaly detection: https://ntrs.nasa.gov/citations/20250005402
- NASA ROSA impact story: https://www.nasa.gov/directorates/stmd/impact-story-roll-out-solar-arrays/
- ESA ECSS-E-ST-20-08C Rev.2: https://ecss.nl/standard/ecss-e-st-20-08c-rev-2-photovoltaic-assemblies-and-components-20-april-2023/
- ESA NIEL model: https://nom.esa.int/models/niel
- AFRL IRENE AE9/AP9/SPM: https://www.vdl.afrl.af.mil/programs/ae9ap9/factsheet.php
- BIRDS EPS dataset: https://github.com/BIRDSOpenSource/EPS_dataset
- SpacePy: https://spacepy.github.io/
- SpiceyPy: https://spiceypy.readthedocs.io/
- Physics-based Cluster degradation framework (Acta Astronautica, 2025): https://doi.org/10.1016/j.actaastro.2024.10.052
- Radiation-induced degradation review (2021): https://doi.org/10.1016/j.solmat.2021.111379
- Space PV environments review (2021): https://doi.org/10.1016/j.apenergy.2021.116757
- Quasi-2D perovskite LEO results (2026): https://pubmed.ncbi.nlm.nih.gov/41677070/

## 11. 2026 IESO workshop implications

The June 2026 DOE IESO Space PV workshop adds a useful community-level roadmap layer to the technical literature. Participants proposed array-level 2035 targets of >200 W/kg specific power, >200 W/m² EOL areal power under AM0, >=70% BOL power retained for a defined mission profile, and <$10/W at a defined hardware boundary. The report explicitly treats these as participant recommendations rather than DOE commitments.

For analytics, the most important contribution is not the numeric target alone but the **reporting context**: cell, CIC, panel/blanket and array values are not directly comparable, and meaningful BOL/EOL metrics require illumination reference, orbit, mission duration and hardware boundary. The repository should therefore make those fields mandatory in technology and performance records.

The workshop also reinforces three research directions already present here:

1. predictive mission-specific degradation, including recovery and combined-stressor effects;
2. shared flight + ground-test data with common provenance and quality metadata;
3. mission- and technology-specific qualification rather than one generic environment model.

See `docs/literature/09_ieso_2026_workshop_roadmap.md` and `docs/product_feature_roadmap.md` for the direct software translation.
