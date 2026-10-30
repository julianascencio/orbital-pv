# 2026 implementation and evidence matrix

Research cutoff: **2026-10-30**. This source-tree expansion translates selected
2024–2026 papers and primary dataset documentation into methods, connectors and
reproducible analyses. Selection favors relevance, usable inputs and independent
validation. It is **not a verified ranking by citation count**; recent 2026 papers
have little citation history and database counts are not interchangeable.

## What is implemented

| Workstream | Actual implementation | Evidence and limits |
| --- | --- | --- |
| Calibration | Least-squares/ridge calibration and a Gaussian Bayesian linear posterior with supplied observation noise. | Parameter-recovery tests and held-out flight forecasting. No GP discrepancy model or exact reproduction of the 2026 Cluster method is claimed. |
| Flight forecasting | Causal V/I lag features, persistence/seasonal baselines and fitted linear forecasts; target-boundary purging. | Actual Flying Laptop measurements, chronological evaluation, horizon-specific MAE. A forecast is not a healthy-PV maximum-power reference. |
| Joint uncertainty | Block-conformal maxima over V/I channels and horizons, finite-sample order statistic and sign-safe product intervals. | Coverage and interval width are both reported. Small calibration sets produce unbounded intervals; row blocks do not prove exchangeability. Not the complete task-aware 2026 algorithm. |
| Thermal/PV coupling | Lumped semi-implicit thermal balance with direct solar, albedo, Earth IR, PV extraction and energy residuals. | Independent analytic cooling benchmark and optional supplied flight CSV. No measured flight thermal validation or physics-informed neural solver is claimed. |
| Radiation | Differential spectrum integration against explicit NIEL and shielding transmission; calibrated retention law. | Analytical/invariant tests and labeled spectra/parameter scenarios. Environment, transmission and retention coefficients require mission/cell calibration. |
| Spectral and tandem PV | EQE-to-photocurrent integration and series-current matching with a wavelength-wise photon-budget check. | Analytical unit checks and synthetic spectral windows. This is not a transfer-matrix optical solver or the full 2026 tandem implementation. |
| Array faults | Series substrings and parallel strings, diode generating branch, series resistance, bypasses and open/short/shaded scenarios. | Circuit behavior and power monotonicity tests. The model omits full avalanche/hotspot dynamics and flight-trained diagnostic classification. |
| EPS/compute | SOC- and power-limited dispatch, curtailment/unserved power, rainflow cycles, calibrated damage, deadline-aware solar-first scheduling and radiator screening. | Conservation and scheduling checks with a declared eight-orbit case. The heuristic is not a global optimum; a damage index is not capacity or qualified life. |
| PV mapping | Published ANDPI index/adaptive rule, geographic holdout benchmark and supplied segmentation callable/weights adapter. | Real cached Cestas/Tenerife scenes and weak reference labels; masking/overlap tests. The full prior-inventory fusion pipeline and pretrained neural papers are not falsely presented as reproduced. |
| Geometry/capacity | Explicit area/capacity definitions, additional geometry covariates, geographic partitions and split-conformal intervals. | Held-out historical inventory experiment. AC/DC basis remains explicit; an inventory site area does not become module area automatically. |
| Construction history | Geometry overlap, split/merge accounting and first-observation date brackets. | Deterministic multi-date scenarios; real imagery/inventory inputs accepted. Observed appearance is not an exact construction or grid-connection date. |
| Irradiance forecasting | Clear-sky persistence, phase correlation, local Lucas–Kanade refinement, advection and issue-time-checked forecast blending. | Synthetic controlled-motion tests and scenarios. Raw geostationary radiance still requires a validated irradiance/cloud retrieval; Baguan-Solar weights are not bundled. |

## Connectors and data contracts

| Input | Implemented access | Verified boundary |
| --- | --- | --- |
| BUPT-1 / SatelliteCOTS | Commit-pinned archive download, hash verification, long/short schema normalization and measured energy accounting. | Real archive inspected. Source-local clocks remain local unless a timezone is explicitly supplied. MPPT input, controller output, battery and bus channels stay separate. Raw archive redistribution rights are not assumed; reference aggregates only. |
| Flying Laptop | Existing official source plus a licensed reduced native V/I snapshot for offline forecasting. | Attribution, source checksum, transformation and clock/cadence are recorded next to the snapshot. |
| NASA CERES | Current CMR collection/edition discovery, paged granules, bounded downloads and CF-netCDF TOA field reader. | Public live catalog verified. Protected file download requires authorized Earthdata access. NASA cloud collection names and versions are separate. |
| Earth-view forcing | Lambertian spherical-grid integration with receiver/source angles, exact grid areas and missing-view reporting. | Independent uniform-Earth limit; rejects impossible geometric view factors. This is an approximation to angular radiance, not direct use of TOA flux as panel irradiance. |
| NOAA POES/MetOp | Native daily downloads, checksum receipts, metadata inspection and detector-channel/time decoding. | Real 43,199-record MetOp day and reduced offline snapshot. Provider contamination warnings, original differential/integral units and processing metadata retained. |
| SPENVIS/IRENE | SPENVIS/UNIRAD block-CSV import, vectors, units, metadata and multi-block validation. | Actual documented interchange format. Generic IRENE files and remote SPENVIS execution are outside this importer. |
| Space-Track | Authenticated historical GP query with mandatory disk cache, time/identity checks and truncation rejection. | Offline HTTP contract tests; user credentials needed for live history. Element epoch differs from publication availability. |
| NAIF/SPICE | Existing kernel retrieval plus UTC-to-ET and frame/attitude vector transforms. | Rotation conventions and error propagation tested; user must supply kernels with required coverage. |
| PNOA | Official WMS capabilities, current/historical layers and geographic image requests. | Native imagery dates/resolution remain provider metadata; output pixel size does not establish native information content. |
| Copernicus Data Space | Official STAC search and selected asset download. | Retrieval/provenance tested; archive and asset access can require account credentials. Existing Earth Search support remains usable. |
| PV inventories | Explicit source assets, checksum/license metadata and GeoJSON or optional vector-file readers. | GMSEUS/Global Renewables Watch metadata supported; underlying commercial imagery rights are not implied by derived polygon access. |
| NOAA GOES ABI | Public NOAA S3 listing and explicit satellite/product/date asset retrieval. | This is imagery/radiance access, distinct from the existing GOES particle connector. Users select the historically correct satellite. |
| EUMETSAT | Official EUMDAC SDK search/download wrapper with caller-supplied access. | Tested through an injected SDK store; live licensed products require user credentials and applicable access terms. |

## Reproducible analyses

Every directory below includes a runner, instructions and an executed reference
result. Generated working exports go under ignored `outputs/`; the checked
reference results are deliberately small and reviewable.

| Directory under `analysis/` | Default evidence |
| --- | --- |
| `bupt1_energy_budget` | Actual pinned spacecraft telemetry; aggregate output, raw download on request. |
| `flight_power_uncertainty` | Actual licensed Flying Laptop observations; offline snapshot. |
| `flight_thermal_validation` | Independent analytic cooling; optional supplied measurement CSV. |
| `radiation_eol_tradeoffs` | Declared spectra, shielding and calibration scenarios. |
| `array_fault_signatures` | Declared circuit fault scenarios. |
| `spectral_cell_comparison` | Declared spectral/EQE scenarios. |
| `orbital_compute_dispatch` | Declared orbital power, storage and workload scenario. |
| `environmental_inputs` | Real NOAA snapshot plus separate analytic Earth-view benchmark and live CERES catalog record. |
| `pv_mapping_generalization` | Real cached ground imagery; geographic holdout and weak labels. |
| `pv_geometry_capacity` | Real historical inventory; held-out geography and capacity definitions. |
| `pv_construction_history` | Labeled constructed geometry/time sequence. |
| `satellite_irradiance_forecasting` | Labeled constructed cloud-motion/irradiance sequence. |

New galleries call only the public `orbitalpv` API and require no credentials
or network during documentation builds. Provider access and model weights are
explicit runtime choices. Numerical invariants, scientific boundary conditions,
chronological/geographic separation and source schemas are tested independently
of the examples.

## Research sources and the implementation they motivate

1. Spacecraft Bayesian calibration (2026), [DOI 10.1016/j.ast.2025.110769](https://doi.org/10.1016/j.ast.2025.110769). Motivates explicit physical-parameter uncertainty and separate discrepancy; the implemented model is a transparent linear Gaussian baseline.
2. Task-aware spacecraft forecasting/envelopes (2026), [DOI 10.1371/journal.pone.0360910](https://doi.org/10.1371/journal.pone.0360910). Motivates coherent V/I/power bounds, later-time evaluation and regime reporting. Data: [SatelliteCOTS pinned revision](https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS/tree/951b41521351d535b7c2354916d9c4991602e8c7).
3. Thermal/PV physics-informed modeling (2026), [DOI 10.1016/j.ast.2026.112268](https://doi.org/10.1016/j.ast.2026.112268). Motivates coupled thermal/electrical state and measured validation requirements, not a claim to reproduce its learned solver.
4. Coupled radiation/thermal PV study (2026), [DOI 10.1016/j.renene.2026.125716](https://doi.org/10.1016/j.renene.2026.125716), and orbital spectral/stress screening, [DOI 10.1016/j.solmat.2026.114518](https://doi.org/10.1016/j.solmat.2026.114518). Motivates explicit environment, spectra and calibrated end-of-life assumptions.
5. Array topology/fault modeling (2026), [DOI 10.1016/j.ast.2026.112139](https://doi.org/10.1016/j.ast.2026.112139). Motivates circuit-level mismatch/bypass scenarios; ground validation does not become flight validation here.
6. Tandem optical framework (2026), [DOI 10.1038/s44172-026-00813-2](https://doi.org/10.1038/s44172-026-00813-2). Motivates spectral/current matching; the present code is not that framework or a copied supplement.
7. Battery-aware scheduling (2026), [DOI 10.1109/ACCESS.2026.3656399](https://doi.org/10.1109/ACCESS.2026.3656399). Motivates solar-aware workloads and cycle-depth reporting; improvements must be measured per mission scenario.
8. Orbital computing constraints (2026 preprint), [arXiv:2604.27197](https://arxiv.org/abs/2604.27197). Motivates joint power/storage/thermal feasibility screening; not a validated deployment forecast.
9. PANEL (2026), [DOI 10.1016/j.isprsjprs.2026.05.012](https://doi.org/10.1016/j.isprsjprs.2026.05.012), [model access](https://huggingface.co/UEXdo/PANEL), and TransPV (2024), [DOI 10.1016/j.apenergy.2023.122282](https://doi.org/10.1016/j.apenergy.2023.122282). Motivate stronger supplied-model comparators and local evaluation. An adapter without the actual weights is not model validation.
10. ANDPI (2025), [DOI 10.1016/j.jag.2025.105005](https://doi.org/10.1016/j.jag.2025.105005), [authors' pinned implementation](https://github.com/SUNNYTREE-LAB/Fusion_PV_Mapping/tree/ba2f0cd340c57c6780ed63770a9a89b855fde54b). The spectral/adaptive rule is implemented with MIT attribution. Prior-inventory fusion must be evaluated separately from unconstrained discovery.
11. GMSEUS (2025 paper; 2026 data update), [DOI 10.1038/s41597-025-05862-4](https://doi.org/10.1038/s41597-025-05862-4), [v2.1 record](https://zenodo.org/records/21445384). Motivates geometry/area/capacity definitions and regional evaluation; modeled optimal tilt is not a measured panel tilt.
12. Global Renewables Watch (2025 preprint), [arXiv:2503.14860](https://arxiv.org/abs/2503.14860), [source repository](https://github.com/microsoft/global-renewables-watch). Motivates dated inventories and growth analysis with explicit imagery rights.
13. PVP-Adapter (2026), [DOI 10.1016/j.isprsjprs.2026.07.032](https://doi.org/10.1016/j.isprsjprs.2026.07.032). Motivates change-focused evaluation; the implemented geometry comparison is a baseline, not its neural architecture.
14. Baguan-Solar (2026 preprint), [arXiv:2603.14845](https://arxiv.org/abs/2603.14845), [authors' repository](https://github.com/DAMO-DI-ML/Baguan-solar). Motivates satellite/NWP forecasting comparisons; benchmark-region transfer and code/weight rights need verification before integration.

## Next evidence-driven work

Add co-timed panel temperature, attitude, illumination, bus/MPPT state and
available-power measurements before attributing forecast residuals to PV health.
Calibrate material-specific NIEL/retention and optical parameters before mission
lifetime claims. Evaluate supplied neural weights against geographic and temporal
holdouts with independently surveyed labels. Add real multi-date construction
labels and a licensed, calibrated weather-satellite irradiance benchmark before
replacing the corresponding constructed scenarios with field-performance claims.
