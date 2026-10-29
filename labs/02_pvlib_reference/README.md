# Lab 02 — pvlib-backed reference PV model

`pvlib` is the reference implementation layer for familiar PV equations, not the complete space-cell model.

Initial uses:

- PVWatts-like calibrated BOL panel reference.
- De Soto / single-diode baseline for single-junction experiments.
- I-V curve utilities and parameter-estimation experiments.

Not assumed valid without additional work:

- terrestrial ambient/wind cell-temperature models,
- atmospheric airmass/spectral models,
- native III-V multi-junction current matching,
- radiation degradation.

Space-specific inputs (AM0, eclipse, AOI, measured/thermal cell temperature, radiation state) are calculated outside pvlib and passed into the adapter.
