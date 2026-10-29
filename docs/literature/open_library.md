# Open literature and data library

_Last access/status review: 2026-09-09_

This is the master reading list for the repository. **OPEN** means a freely accessible full text/public report was identified. **PUBLIC-DATA** means an open dataset/API. **WATCH** means the work is technically important but unrestricted full-text access should not be assumed.

## A. State of practice / reviews

| Status | Year | Source | Why it matters |
|---|---:|---|---|
| OPEN | 2026 | [NASA Small Spacecraft State-of-the-Art — Power](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/) | Best current public engineering baseline for flight/practical SmallSat power technology; III-V 3–5J, arrays, specific power, EOL considerations. |
| OPEN | 2026 | [Space Photovoltaics: Materials, Device Concepts and Operational Challenges](https://www.mdpi.com/2079-9292/15/10/1978) | Broad space-PV review linking AM0, radiation, thermal cycling, III-V, tandems and emerging devices. |
| OPEN | 2025 | [Advances in multijunction solar cells: An overview](https://doi.org/10.1016/j.seja.2025.100105) | Current multijunction device/fabrication review; useful for III-V/IMM model roadmap. |
| OPEN | 2025 | [Comprehensive analysis of CubeSat electrical power systems for efficient energy management](https://link.springer.com/article/10.1007/s43937-025-00069-5) | EPS architecture and energy-management context for SmallSats. |
| OPEN | 2024 | [Technical challenges of space solar power stations: ultra-large-scale solar array systems and environmental effects](https://doi.org/10.1016/j.sspwt.2024.09.003) | System-level array/environment challenges at very large scale. |

## B. Modelling, telemetry calibration and digital twins

| Status | Year | Source | Why it matters |
|---|---:|---|---|
| OPEN | 2024 | [NASA — Solar Array Performance Modeling for Artemis Missions](https://ntrs.nasa.gov/citations/20240010780) | Mission-aware model with eclipse, pointing constraints and radiation; flight comparison context. |
| OPEN | 2025 | [Developing a modelling environment of spacecraft solar array in LEO using real-time telemetry](https://doi.org/10.1016/j.fraope.2025.100268) | Open LEO GaAs thermal/electrical/mission model validated with spacecraft telemetry. |
| OPEN | 2025 | [Institutional full-text copy of the LEOS-50 modelling paper](https://repository.msa.edu.eg/items/d725ab64-695a-4825-a7db-c391188af88e) | Stable open full-text route. |
| OPEN | 2025 | [ESA Cluster — Digital Twin Solution for Solar Array Degradation / Power Prediction](https://publications.spaceops.org/2025/download_by_id.php?id=0013) | Physics + Bayesian calibration + monitoring + ML; closest published analogue to the target repo architecture. |
| OPEN | 2024 | [Implementation of a 6U CubeSat Electrical Power System Digital Twin](https://www.mdpi.com/2226-4310/11/8/688) | Open implementation example; triple-junction sections represented with single-diode model. |
| WATCH | 2025 | [Physics-based degradation framework applied to ESA Cluster](https://doi.org/10.1016/j.actaastro.2024.10.052) | Simplified physics model + evolutionary calibration against real Cluster monitoring data. |
| WATCH | 2026 | [Robust calibration and model discrepancy reduction for ESA Cluster digital twin](https://doi.org/10.1016/j.ast.2025.110769) | Bayesian calibration + Gaussian-process discrepancy; important for uncertainty/RUL. |
| WATCH | 2026 | [Telemetry-driven physics-informed thermal–electrical prediction](https://doi.org/10.1016/j.ast.2026.112268) | TSURU telemetry, energy-balance and PV constraints; direct PIML frontier. |
| WATCH | 2026 | [Photo–thermal–electrical coupling degradation model under long-term space radiation](https://doi.org/10.1016/j.renene.2026.125716) | Multi-physics degradation structure; useful model-design reference. |

## C. Radiation and degradation

| Status | Year | Source | Why it matters |
|---|---:|---|---|
| OPEN | 2025 | [Semiconductor Material Damage Mechanisms Due to Non-Ionizing Energy in Space-Based Solar Systems](https://www.mdpi.com/1996-1073/18/3/509) | Recent NIEL/DDD treatment across orbit classes. |
| OPEN | 2021 | [A short review of radiation-induced degradation of III–V photovoltaic cells for space applications](https://doi.org/10.1016/j.solmat.2021.111379) | Compact reference for III-V proton/electron degradation models. |
| OPEN | 2025 | [On-Orbit Life Prediction of Triple-Junction GaAs Solar Arrays for MEO Satellites](https://www.mdpi.com/2226-4310/12/7/633) | Seven-year MEO life/degradation case using theoretical + flight data. |
| OPEN | 2025 | [Radiation-induced degradation in optoelectronic devices for satellite applications: a review](https://link.springer.com/article/10.1007/s43939-025-00185-y) | Broader radiation-effects review. |
| OPEN | public | [IRENE / AE9 / AP9 / SPM factsheet](https://www.vdl.afrl.af.mil/programs/ae9ap9/factsheet.php) | Modern near-Earth trapped-particle model family, including uncertainty outputs. |
| OPEN | public | [IRENE documents / APIs](https://www.vdl.afrl.af.mil/programs/ae9ap9/documents.php) | User guides, technical docs and Python API references. |
| OPEN | public | [ESA Network of Models — IRENE](https://nom.esa.int/models/irene) | ESA/SPENVIS integration path. |

## D. Emerging and alternative PV technologies

| Status | Year | Source | Why it matters |
|---|---:|---|---|
| OPEN | 2023 | [Six years of AlSat-1N thin-film CdTe solar-cell flight results](https://doi.org/10.1016/j.actaastro.2023.08.034) | Rare multi-year flight evidence for lightweight thin film. |
| OPEN | 2024 | [Toward Rollable Printed Perovskite Solar Cells for LEO](https://doi.org/10.1021/acsaem.3c02761) | Flexible/rollable manufacturing and specific-power direction. |
| OPEN | 2024 | [Advancements in radiation resistance of perovskite solar cells in space](https://pubs.rsc.org/en/content/articlehtml/2024/ta/d3ta06388g) | Radiation-hardness mechanisms and reinforcement strategies. |
| OPEN | 2026 | [Perovskite solar cells for low Earth orbit space applications](https://www.oaepublish.com/articles/energymater.2025.162) | LEO-focused mini review and specific-power framing. |
| OPEN | 2026 | [Perovskite Solar Cells for Space Applications: Progress, Perspectives, and Remaining Challenges](https://www.mdpi.com/1996-1073/19/6/1432) | Current space-perovskite perspective. |
| OPEN | 2026 | [Stability and Degradation of Perovskite Solar Cells in Space Environments](https://www.mdpi.com/1422-0067/27/8/3459) | Degradation mechanisms and testing protocol discussion. |
| OPEN | 2026 | [Thermal-shock resilience and near-space balloon testing of perovskites](https://doi.org/10.1039/D5EE03704B) | Realistic rapid thermal-cycle protocol and near-space validation. |
| OPEN | 2026 | [Beyond Earth: Resilience of Quasi-2D Perovskite Solar Cells in Space — Caltech repository](https://authors.library.caltech.edu/records/9brt4-5mb24) | Real LEO data + ground proton/temperature comparison; major evidence milestone. |
| WATCH | 2025 | [Full Device Evaluation of Metal Halide Perovskite Solar Cells in LEO aboard ISS](https://doi.org/10.1002/smll.202508232) | MISSE device/film results; identifies contact/interface/ion-migration limitations. |
| OPEN | 2026 | [Silicon's cosmic comeback: ultra-thin silicon heterojunction cells for space](https://doi.org/10.1016/j.mtener.2026.102245) | Specific-power + radiation/annealing case for ultrathin Si. |
| OPEN | 2026 | [Rigid-flex PCB deployable solar array for CubeSats](https://doi.org/10.1016/j.actaastro.2025.10.046) | Flight-tested deployment/packaging innovation. |
| OPEN | 2025 | [High-Specific Power Flexible Photovoltaics from Large-Area MoS2 for Space Applications](https://pubs.acs.org/doi/10.1021/acsaem.4c01797) | Exploratory ultrathin/2D-material specific-power direction. |

## E. Telemetry analytics / ML

| Status | Year | Source | Why it matters |
|---|---:|---|---|
| OPEN | 2024 | [Explainable anomaly detection in spacecraft telemetry](https://doi.org/10.1016/j.engappai.2024.108083) | Real NASA telemetry; explainability and feature-driven anomaly detection. |
| OPEN | 2025 | [A Review of Anomaly Detection in Spacecraft Telemetry Data](https://www.mdpi.com/2076-3417/15/10/5653) | Recent survey of telemetry anomaly methods and limitations. |
| OPEN | 2025 | [NASA — Hybrid Model and Data Driven Approach for Anomaly Detection in Space Power Systems](https://ntrs.nasa.gov/citations/20250005402) | Direct evidence for hybrid power-system monitoring. |
| OPEN | 2025 | [Synthetic satellite telemetry data for machine learning](https://link.springer.com/article/10.1007/s12567-024-00589-1) | Addresses label scarcity / synthetic data methodology. |
| OPEN | 2025 | [Degradation Modeling and Telemetry-Based Analysis of Solar Cells in LEO for Nano- and Pico-Satellites](https://www.mdpi.com/2076-3417/15/16/9208) | Direct telemetry + degradation modelling reference. |

## F. Open datasets and APIs

| Status | Source | Contents |
|---|---|---|
| PUBLIC-DATA | [BIRDS EPS GitHub](https://github.com/BIRDSOpenSource/EPS_dataset) | Panel/battery V-I-T telemetry from four CubeSats; panel failures. |
| PUBLIC-DATA | [BIRDS Mendeley Data](https://data.mendeley.com/datasets/8kp25ycf63/1) | DOI-backed BIRDS dataset. |
| OPEN | [BIRDS Data in Brief article](https://pmc.ncbi.nlm.nih.gov/articles/PMC9679683/) | Data description and acquisition details. |
| PUBLIC-DATA | [SatNOGS DB API](https://db.satnogs.org/api/schema/docs/) | Satellite metadata, TLE history, telemetry/decoded frames. |
| PUBLIC-DATA | [SatNOGS API documentation](https://docs.satnogs.org/projects/satnogs-db/en/stable/api.html) | Open API terms and usage. |
| PUBLIC-DATA | [NASA CDAWeb HAPI](https://cdaweb.gsfc.nasa.gov/hapi) | Standardized heliophysics time series. |
| PUBLIC-DATA | [NOAA SWPC JSON services](https://services.swpc.noaa.gov/json/) | Near-real-time space weather. |
| PUBLIC-DATA | [CelesTrak](https://celestrak.org/) | Public orbital elements/catalog. |
| PUBLIC-DATA | [NASA SSCWeb services](https://sscweb.gsfc.nasa.gov/WebServices/) | Spacecraft ephemerides / related products. |
| PUBLIC-DATA | [NASA NAIF kernels](https://naif.jpl.nasa.gov/naif/data.html) | Mission trajectory/attitude/frame kernels. |

## G. Spectrum / reference environments

| Status | Source | Notes |
|---|---|---|
| STANDARD | [ASTM E490-22 landing page](https://store.astm.org/standards/e490) | Active AM0 reference standard; paid/copyrighted standard. |
| PUBLIC-DATA | [Public ASTM E490 reference spectrum distribution](https://www.nlr.gov/grid/solar-resource/spectra-astm-e490) | Older reference spectrum useful for reproducible open experiments; record version explicitly. |

## H. Software foundations

| Status | Source | Role |
|---|---|---|
| OPEN-SOURCE | [pvlib-python](https://github.com/pvlib/pvlib-python) | Tested PV equations; space adapter, not complete space model. |
| OPEN-SOURCE | [Skyfield](https://github.com/skyfielders/python-skyfield) | Time/ephemeris/satellite geometry. |
| OPEN-SOURCE | [python-sgp4](https://github.com/brandon-rhodes/python-sgp4) | Vallado SGP4 implementation. |
| OPEN-SOURCE | [Astropy](https://github.com/astropy/astropy) | Time/coordinates/units. |
| OPEN-SOURCE | [SpiceyPy](https://github.com/AndrewAnnex/SpiceyPy) | Python CSPICE wrapper. |
| PUBLIC-DATA/SOFTWARE | [NASA NAIF SPICE](https://naif.jpl.nasa.gov/) | Mission ephemeris / geometry standard. |

## I. Space-based solar power / commercial energy delivery

| Status | Year | Source | Why it matters |
|---|---:|---|---|
| NEWS | 2026 | [pv magazine — Virtus Solis / Brae 100 MW PPA](https://pv-magazine-usa.com/2026/10/01/virtus-solis-signs-ppa-to-supply-space-based-solar-power-to-datacenter-developer-brae-systems/) | Commercial/offtake signal for SBSP + AI/datacenter load; infrastructure not yet deployed. |
| PRIMARY-COMPANY | 2026 | [Virtus Solis — PPA announcement](https://www.virtussolis.space/blog/virtus-solis-signs-landmark-20-year-ppa-with-brae-systems) | Confirms initial 100 MW, 876,000 MWh/year and 250 MW option. |
| PRIMARY-COMPANY | 2026 | [Virtus Solis — technology architecture](https://www.virtussolis.space/our-technology) | Molniya, 10 GHz, modular satellite and rectenna design claims; use as proposed parameters only. |
| OPEN | 2024 | [NASA OTPS — Space-Based Solar Power](https://ntrs.nasa.gov/citations/20230018600) | Independent system/economics baseline and capability-gap analysis. |
| OPEN | 2024 | [NASA ASCEND SBSP lifecycle study](https://ntrs.nasa.gov/citations/20240008752) | Reports baseline lifecycle energy-cost gap and sensitivity to launch/manufacturing improvements. |
| OPEN | 2024 | [ESA — SOLARIS / Solar Power Satellites and WPT](https://activities.esa.int/cluster/923) | European SBSP system studies, R&D activities and demonstration context. |
| WATCH | 2024 | [Simultaneous orbit and attitude optimization of planar arrays for SBSP beaming](https://www.sciencedirect.com/science/article/pii/S0094576524001802) | Molniya-orbit/attitude optimization; funded by Virtus Solis, so provenance matters. |
| OPEN | 2025 | [Space solar power generation: system proposal and technoeconomic analysis](https://www.sciencedirect.com/science/article/pii/S2542435125001096) | Modern modular RF/solar architecture and technoeconomic model; reports a favorable future-cost scenario. |

## 2026 IESO Space Photovoltaics Workshop

- **OPEN / workshop synthesis** — U.S. DOE Integrated Energy Systems Office, *2026 IESO Space Photovoltaics Workshop: Findings and Participant Recommendations — Technical Priorities for Next-Generation Space Photovoltaics* (June 2026 workshop; report provided to this project in October 2026).
- **Why it matters:** quantitative array-level 2035 targets; technology-family priorities; mission-specific environment and qualification recommendations; combined-stressor testing; open flight/test data registry; phased 1–3 year / 3–7 year / 2035 roadmap.
- **Repository note:** see `09_ieso_2026_workshop_roadmap.md` for the translation into features and data contracts.
