# Connector catalog

The connector layer retrieves raw external facts and preserves provenance. It does not perform analytics.

| Connector | Data | Auth | Primary use |
|---|---|---:|---|
| CelesTrak GP | OMM/TLE/CSV satellite orbital elements | No | Current public catalog orbits |
| Space-Track | GP + historical element sets/catalog | Yes | Authoritative catalog history and broader SSA queries |
| NASA SSCWeb | definitive/predictive ephemeris for many science spacecraft | No | Real spacecraft positions without maintaining all mission kernels |
| NASA NAIF | SPICE SPK/CK/FK/PCK/LSK/SCLK kernels | No | Mission-grade geometry, attitude, time/frame transforms |
| NASA CDAWeb HAPI | heliophysics mission time series | No | Real space-environment/science measurements |
| NOAA SWPC | Kp, F10.7, solar wind; normalized measured GOES integral proton/electron flux | No | Geostationary particle environment, with energy thresholds and actual spacecraft identity |
| ESA DISCOS | spacecraft/object/launch metadata | Account/API terms | Physical/mission metadata; not ephemeris |
| NASA NTRS | report search, citation metadata and available original documents | No | Evidence discovery for array ratings and specifications; extraction/review required |
| Zenodo | published dataset search, versions, licenses, checksum-verified open downloads | No for public records/files | Discover additional flight/experimental datasets; restricted files stay restricted |
| Dataverse / DaRUS | public dataset search, published versions and checksum-verified original downloads | No for public datasets/files | General dataset discovery, complementing the specialized Flying Laptop loader |
| JPL Horizons | geometric vectors for supported spacecraft/other targets | No | Sun-relative illumination inputs; explicit ICRF, TDB, AU/day; no array attitude |
| NASA PDS | product search and identifier resolution | No | Mission archive discovery; engineering data availability varies |
| ESA PSA TAP | bounded ADQL SELECT queries with column units and product links | No for public products | ESA mission products; no universal EPS telemetry |
| NASA CCMC DONKI | flares, CMEs, SEP and other space-weather events | No through direct CCMC API | Event context; not spacecraft-specific dose or proof of PV degradation |
| SatNOGS DB | satellite metadata and TLEs; telemetry endpoint | Metadata public; telemetry requires credentials | Do not assume anonymous decoded telemetry access; telemetry returned HTTP 401 in the access check |
| BIRDS EPS | panel/battery V/I/T telemetry | No | Open real PV/EPS benchmark |
| Flying Laptop / DaRUS | calibrated four-array voltage/current and derived V×I, UTC packet timestamps | No | Measured on-orbit generation; monthly archives, DOI 10.18419/darus-451, CC BY 4.0 |
| OPS-SAT-AD v2 | original photodiode/magnetometer segments and expert anomaly annotations | No | Sensor/illumination-related benchmark; units unspecified in source, DOI 10.5281/zenodo.15108715, CC BY 4.0 |
| LASP LISIRD | TSIS-1/SORCE measured total irradiance; TSIS-1 measured spectral irradiance | No | Real illumination inputs in W/m² or W/m²/nm; 1-AU and actual-Earth-distance fields, uncertainties and quality flags |
| Earth Search / Sentinel-2 Collection 1 | STAC scene metadata, RGB, spectral bands and scene classification | No | Native-resolution ground-image crops and GeoTIFF export; optional Rasterio; no implicit reflectance conversion or cloud masking |
| OpenStreetMap / Overpass | Raw solar/wind nodes, ways and relations with tags and geometry | No | Small-area mapping inputs following Dunnett et al.'s source-tag selection, with legacy tags included; no farm clustering or capacity estimation |

The [ground imagery guide](https://julianascencio.github.io/orbital-pv/user_guide/modeling_topics/ground_imagery.html)
and [Cestas gallery walkthrough](https://julianascencio.github.io/orbital-pv/gallery/ground_imagery/plot_ground_satellite_inputs.html)
show how image and OSM snapshots remain distinct, with acquisition dates, source licenses and checksums.

## Executable measurement examples

The [free research API guide](https://julianascencio.github.io/orbital-pv/user_guide/modeling_topics/research_connectors.html)
documents all eight implemented research adapters, explicit pagination and
query/checksum-bound caches. Its [offline gallery example](https://julianascencio.github.io/orbital-pv/gallery/real_data/plot_research_connectors.html)
uses original responses from seven anonymous services. DISCOS requires a free
account/token and was contract-tested without live credentials. Re-run the
opt-in access check with `python scripts/check_research_connectors.py`.

The [real-data gallery](https://julianascencio.github.io/orbital-pv/gallery/real_data/index.html) uses the public `orbitalpv` API for every connector:

- [Flying Laptop measured generation](https://julianascencio.github.io/orbital-pv/gallery/real_data/plot_flying_laptop_power.html): February 2018, 75,097 packet times and 300,388 array observations.
- [OPS-SAT original telemetry](https://julianascencio.github.io/orbital-pv/gallery/real_data/plot_opssat_photodiode_telemetry.html): 303,493 measured values across 2,123 annotated segments and nine channels.
- [Measured total irradiance](https://julianascencio.github.io/orbital-pv/gallery/real_data/plot_lisird_measured_irradiance.html): TSIS-1 annual coverage and overlap with SORCE; provider missing-value bins remain missing.
- [Measured solar spectrum](https://julianascencio.github.io/orbital-pv/gallery/real_data/plot_lisird_measured_spectrum.html): three daily TSIS-1 spectra, 2,104 wavelength bins per spectrum, with quality bits preserved.
- [GOES measured particle environment](https://julianascencio.github.io/orbital-pv/gallery/real_data/plot_goes_measured_particle_flux.html): a cached seven-day snapshot, with actual observation and retrieval times printed.
- [BIRDS measured EPS telemetry](https://julianascencio.github.io/orbital-pv/gallery/real_data/plot_birds_raavana_real_data.html): four spacecraft and 48 flight campaigns.

See [source evidence and limitations](real_measurements.md) for the primary references, units, access checks and interpretation boundaries.

## Canonical lake tables

```text
bronze.satellite_catalog
bronze.orbit_elements
bronze.ephemeris_state
bronze.attitude_state
bronze.pv_telemetry
bronze.space_weather
bronze.radiation_flux
bronze.mission_metadata

silver.sun_geometry
silver.array_effective_irradiance
silver.expected_pv
silver.pv_residuals

gold.performance_kpi
gold.degradation_state
gold.anomaly_events
```

Every raw download should eventually have an `input_manifest.json` containing source, request/query, retrieval timestamp, SHA-256, units/frame assumptions, and license/attribution notes.
