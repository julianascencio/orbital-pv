# Lab 01 — Orbit + Sun geometry foundation

This lab shows the live-orbit workflow through the **public `orbitalpv` package**.

## Install

```bash
python -m pip install "orbital-pv[orbit]"
```

## Run

```bash
python labs/01_orbit_sun_geometry/run_celestrak.py
```

## Public API workflow

```python
import orbitalpv as opv

omm = opv.fetch_celestrak_omm(25544)
satellite = opv.satellite_from_omm(omm)
positions_m, velocities_m_s = opv.propagate_geocentric_m(satellite, times)
sun_positions_m = opv.geocentric_sun_positions_m(times)
geometry = opv.solar_geometry(positions_m[0], sun_positions_m[0])
```

Persist the retrieved OMM when reproducibility matters.
