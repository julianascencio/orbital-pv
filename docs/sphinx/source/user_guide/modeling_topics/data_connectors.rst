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
