# Foundation stack

## 1. Time, frames and units — Astropy

Astropy is the common scientific layer for UTC/TAI/TT handling, coordinates, frames and units. Its `get_sun()` path gives a convenient geocentric Sun vector for baseline work. For higher-fidelity mission work, use JPL/SPICE ephemerides consistently rather than mixing sources silently.

## 2. Earth satellite propagation — Skyfield + python-sgp4

For public catalog satellites, ingest OMM from CelesTrak/Space-Track and propagate with Skyfield's `EarthSatellite`, which uses the maintained Vallado SGP4 implementation. OMM is preferred over legacy TLE storage in our canonical model.

## 3. Mission ephemeris and attitude — SpiceyPy / NASA SPICE

SPICE becomes the high-fidelity path when SPK/CK/FK/SCLK kernels exist. It covers spacecraft/planet geometry, reference frames, clocks and attitude. Keep kernels as versioned raw inputs with manifests.

## 4. PV equations — pvlib behind a space adapter

Do not call terrestrial `ModelChain` directly for spacecraft. Reuse tested pvlib equations where applicable, while replacing Earth-specific inputs:

```text
Sun distance -> AM0
Earth occultation -> illumination fraction
attitude + panel normal -> cos(AOI)
thermal telemetry/model -> cell temperature
radiation state -> degraded electrical parameters
                    |
                    v
              pvlib-backed equation
```

PVWatts is useful as an engineering baseline after AM0/BOL calibration. De Soto/single-diode is useful for single-junction cells. III-V multi-junction requires a dedicated model layer on top of or beside pvlib.

## 5. Later numerical/high-fidelity dynamics

Orekit is a mature recognized flight-dynamics library and can be added through a Python adapter when we need force models, event detection, estimation or operational-grade propagation beyond SGP4/SPICE products. It is not the default because the Python route crosses a Java wrapper/JVM boundary. `satkit` is worth benchmarking later for Rust-backed high-performance propagation.

## Explicit non-choice: poliastro

Do not make archived poliastro a foundational dependency. Historical notebooks may use it, but new core code should not.
