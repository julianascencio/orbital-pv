.. _package_overview:

Package Overview
================

OrbitalPV is a workspace rather than one large Python module. Each package has
one primary responsibility.

Scientific packages
-------------------

``space-pv-core``
   Stable domain contracts and physical constants.

``space-pv-orbit``
   Orbit propagation adapters, attitude transforms, Sun geometry, incidence
   angle, and eclipse calculations.

``space-pv-pvmodel``
   Space-specific PV modelling adapters. It reuses validated pvlib equations
   where appropriate without assuming a terrestrial PV system model is a
   spacecraft model.

``space-pv-space-env``
   AM0 irradiance and the evolving space-environment/radiation layer.

``space-pv-connectors``
   External data adapters for orbital elements, mission ephemerides, space
   weather, and open spacecraft telemetry.

``space-pv-analytics``
   Performance normalization, degradation, persistent-loss, residual, and
   health analytics.

Platform packages
-----------------

``space-pv-storage``
   DuckDB analytics and PostgreSQL/PostGIS application persistence.

``space-pv-orchestration``
   Celery task orchestration. Scientific packages do not depend on Celery.

Applications
------------

``space-pv-cli``
   Command-line workflows and reproducible experiment entry points.

``space-pv-api``
   FastAPI boundary for jobs, data products, and map-serving endpoints.

``space-pv-web``
   React/Cesium frontend. This application is intentionally outside the Python
   workspace.

Design principles
-----------------

1. Physics before machine learning where a physical model is available.
2. Coordinate frame, time scale, unit, and source provenance are first-class.
3. Raw source data and derived scientific products remain separate.
4. Long-running orchestration stays outside scientific packages.
5. Flight-data analytics should compare measured power with expected physical
   power rather than relying on raw power thresholds alone.
