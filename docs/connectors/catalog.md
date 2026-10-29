# Connector catalog

The connector layer retrieves raw external facts and preserves provenance. It does not perform analytics.

| Connector | Data | Auth | Primary use |
|---|---|---:|---|
| CelesTrak GP | OMM/TLE/CSV satellite orbital elements | No | Current public catalog orbits |
| Space-Track | GP + historical element sets/catalog | Yes | Authoritative catalog history and broader SSA queries |
| NASA SSCWeb | definitive/predictive ephemeris for many science spacecraft | No | Real spacecraft positions without maintaining all mission kernels |
| NASA NAIF | SPICE SPK/CK/FK/PCK/LSK/SCLK kernels | No | Mission-grade geometry, attitude, time/frame transforms |
| NASA CDAWeb HAPI | heliophysics mission time series | No | Real space-environment/science measurements |
| NOAA SWPC | Kp, F10.7, solar wind, GOES and alerts | No | Near-real-time space-weather context |
| ESA DISCOS | spacecraft/object/launch metadata | Account/API terms | Physical/mission metadata; not ephemeris |
| SatNOGS DB | satellite metadata, TLEs, decoded downlink telemetry | No | Large open source of real satellite telemetry; mission-dependent EPS/ADCS fields |
| BIRDS EPS | panel/battery V/I/T telemetry | No | Open real PV/EPS benchmark |

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
