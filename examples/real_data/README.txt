Real on-orbit data
==================

These examples retrieve and analyze public spacecraft telemetry rather than
synthetic data.

The first workflow uses the BIRDS Electrical Power System dataset published by
Jara et al. (2022), DOI 10.17632/8kp25ycf63.1. It contains measured solar-panel
voltage, current and temperature from four 1U CubeSats in low Earth orbit.

Because these examples retrieve live upstream files, they require network
access and the ``excel`` optional dependency.
