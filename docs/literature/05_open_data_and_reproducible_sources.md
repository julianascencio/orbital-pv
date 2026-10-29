# Open data and reproducible sources

_Last reviewed: 2026-09-09_

The biggest practical constraint in space-PV analytics is not lack of algorithms; it is lack of openly available, time-aligned flight data. This page identifies sources that can support reproducible work now.

## 1. Tier A — direct PV / EPS telemetry

### BIRDS EPS dataset — highest priority

**Access:** PUBLIC-DATA  
**What it gives:** solar-panel and battery voltage/current/temperature from four 1U CubeSats; known panel failures on two spacecraft.  
**Use:** degradation, change detection, panel imbalance, thermal/electrical modelling, ML benchmarks.  
**Links:**
- https://github.com/BIRDSOpenSource/EPS_dataset
- https://data.mendeley.com/datasets/8kp25ycf63/1
- https://pmc.ncbi.nlm.nih.gov/articles/PMC9679683/

### SatNOGS DB / Network

**Access:** PUBLIC-DATA, CC BY-SA APIs.  
**What it gives:** satellite metadata, TLEs/historical TLEs, observations and telemetry objects; decoded telemetry availability varies by satellite.  
**Use:** discover satellites with EPS/ADCS fields, reconstruct orbital state, ingest community downlinks.  
**Links:**
- https://db.satnogs.org/api/schema/docs/
- https://docs.satnogs.org/projects/satnogs-db/en/stable/api.html
- https://librespacefoundation.gitlab.io/satnogs/satnogs-network/api.html

**Research priority:** build an automated catalog that scans decoded telemetry schemas for terms such as `solar`, `panel`, `current`, `voltage`, `temperature`, `sun vector`, `quaternion`, `battery`, `eps`.

## 2. Tier A — orbit / ephemeris / attitude

### CelesTrak

Use for public OMM/TLE orbital elements and catalog discovery. Prefer OMM-style records in new pipelines where available.

- https://celestrak.org/

### Space-Track

Use for authoritative public catalog access and historical element sets where account terms permit automated use.

- https://www.space-track.org/

### NASA SSCWeb

Provides ephemeris and related data for supported spacecraft; useful when a mission has better-quality definitive/predictive ephemeris than public TLE propagation.

- https://sscweb.gsfc.nasa.gov/WebServices/

### NASA NAIF / SPICE

Mission kernels can provide high-fidelity trajectory, frames and — where available — attitude/instrument geometry.

- https://naif.jpl.nasa.gov/naif/data.html

## 3. Tier A — space environment

### IRENE / AE9 / AP9 / SPM

Public radiation-environment model and documentation; current public release information is available from AFRL.

- https://www.vdl.afrl.af.mil/programs/ae9ap9/
- https://www.vdl.afrl.af.mil/programs/ae9ap9/documents.php

### ESA Network of Models / SPENVIS

Useful for environment/effects model access including IRENE and NIEL-related workflows.

- https://nom.esa.int/
- https://nom.esa.int/models/irene

### NASA CDAWeb / HAPI

Standardized heliophysics time-series access for solar wind, radiation and magnetospheric context.

- https://cdaweb.gsfc.nasa.gov/hapi

### NOAA SWPC

Near-real-time space-weather context and JSON services.

- https://services.swpc.noaa.gov/json/

## 4. Solar spectrum references

### ASTM E490

ASTM E490-22 is the active standard for the solar constant / zero-air-mass spectral irradiance used in spacecraft work, but the standard itself is commercial.

- ASTM landing page: https://store.astm.org/standards/e490

For reproducible experiments, an older ASTM E490 reference spectrum is openly distributed by the U.S. national-lab solar-resource site:

- https://www.nlr.gov/grid/solar-resource/spectra-astm-e490

**Important:** record the exact spectral dataset/version used in every experiment. Do not silently mix the older E490 spectrum with newer total-solar-irradiance constants.

## 5. Flight-test literature with reusable information

### SSPD-1 / ALBA perovskites

The Caltech repository hosts an open copy and supporting files for the 2026 quasi-2D perovskite LEO study.

- https://authors.library.caltech.edu/records/9brt4-5mb24

This is a strong example of the kind of in-flight PV dataset the project should seek to reproduce structurally: timestamped electrical measurements + temperature + orbit context + ground irradiation tests.

### ESA Cluster digital twin

The SpaceOps paper is freely downloadable and provides an operational degradation/digital-twin case study.

- https://publications.spaceops.org/2025/download_by_id.php?id=0013

### NASA Artemis array modelling

Public NASA presentation documenting mission-level solar-array performance modelling and comparison with flight data.

- https://ntrs.nasa.gov/citations/20240010780

## 6. Proposed connector coverage matrix

| Source | Orbit | Attitude | PV/EPS | Thermal | Radiation | Near-real-time |
|---|---:|---:|---:|---:|---:|---:|
| BIRDS | partial/reconstruct | no/limited | **yes** | **yes** | external join | no |
| SatNOGS | TLE + metadata | mission-dependent | mission-dependent | mission-dependent | external join | often |
| CelesTrak | **yes** | no | no | no | no | yes |
| Space-Track | **yes** | no | no | no | no | yes |
| SSCWeb | **yes** | limited/product-dependent | no | no | environment products vary | yes/archival |
| SPICE | **yes** | **yes if CK exists** | no | no | no | mostly archival |
| CDAWeb/HAPI | context | no | no | some missions | **yes/context** | yes/archival |
| NOAA SWPC | no | no | no | no | **space weather** | **yes** |
| IRENE/SPENVIS | trajectory input | no | no | no | **modeled** | model |

## 7. Reproducibility metadata every ingestion should retain

```text
source
source_url / API endpoint
request parameters
retrieved_at UTC
source version / product version
original timestamp scale
coordinate frame
units
quality flags
license / usage terms
raw hash
parser version
```

Without this metadata, later scientific comparisons become difficult to audit.
