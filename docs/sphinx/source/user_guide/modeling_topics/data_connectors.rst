Data Connectors
===============

Connectors retrieve external facts and preserve provenance. They do not contain
performance analytics logic.

Current sources
---------------

OrbitalPV contains initial adapters for:

* CelesTrak — public orbital elements;
* Space-Track — authenticated catalog access;
* NASA SSCWeb — spacecraft ephemeris services;
* NASA NAIF — SPICE kernels;
* NASA CDAWeb/HAPI — heliophysics time series;
* NOAA SWPC — space-weather context;
* SatNOGS DB — satellite metadata and mission-dependent telemetry;
* BIRDS EPS — open panel and battery telemetry.

Real BIRDS EPS telemetry
------------------------

OrbitalPV can retrieve the public BIRDS Electrical Power System dataset
directly from the upstream BIRDSOpenSource repository:

.. code-block:: python

   import orbitalpv as opv

   telemetry = opv.fetch_birds_eps(
       "RAAVANA",
       "RAAVANA.xlsx",
   )

The helper preserves the original workbook locally and returns normalized
panel-level telemetry with timestamp, panel identifier, voltage, current and
temperature when available.

The dataset is real on-orbit telemetry from four 1U CubeSats and is published
as Jara et al. (2022), DOI 10.17632/8kp25ycf63.1. The associated paper reports
panel failures in RAAVANA and UGUISU, making the data useful for exploratory
fault/anomaly workflows.

See the executable :doc:`../../gallery/real_data/plot_birds_raavana_real_data`
walkthrough for step-by-step graphics from ingestion through health screening.

Provenance contract
-------------------

Every serious ingestion workflow should retain:

* source and endpoint;
* request parameters;
* retrieval timestamp;
* source/product version;
* original time scale;
* coordinate frame;
* units and quality flags;
* raw checksum;
* parser version;
* licensing or usage constraints.

This information is required to reproduce later modelling results.
