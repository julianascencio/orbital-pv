# Lab 01 — Orbit + Sun geometry foundation

Goal: turn orbital state into the geometry needed by PV analytics.

Pipeline:

```text
CelesTrak / Space-Track OMM
        |
        v
Skyfield + Vallado SGP4 -----> spacecraft r,v in time
        |
Astropy / JPL / SPICE -------> Sun vector
        |
        v
Earth occultation + panel attitude -> illumination fraction + cos(AOI)
        |
        v
AM0 irradiance -> effective irradiance -> PV model
```

Use Skyfield/SGP4 for Earth-orbit catalog objects. Use SpiceyPy when a mission publishes SPICE kernels or when attitude/planetary geometry needs mission-grade kernels.
