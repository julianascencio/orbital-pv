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
directly from the upstream BIRDSOpenSource repository. Install the workbook
reader and plotting dependencies to run the gallery example:

.. code-block:: bash

   pip install -U "orbital-pv[excel,examples]>=0.4.2"

Use the public API to download a workbook once and reuse it locally:

.. code-block:: python

   from pathlib import Path

   import orbitalpv as opv

   workbook = Path("data/birds/TSURU.xlsx")
   if workbook.exists():
       telemetry = opv.load_birds_eps_workbook(workbook, campaign_year=2021)
   else:
       telemetry = opv.fetch_birds_eps(
           "TSURU", workbook, campaign_year=2021
       )

``fetch_birds_eps`` preserves the original workbook locally and returns
normalized panel-level telemetry with timestamp, panel identifier, voltage,
current and temperature when available. ``load_birds_eps_workbook`` reads an
existing workbook without another network request. Both preserve the source
sheet so each measurement remains associated with its campaign.

Available measurements
^^^^^^^^^^^^^^^^^^^^^^^^

The expanded example uses all four spacecraft. The following counts describe
the upstream workbooks at commit
``67ad4435c5329abde65afc16e30d725cd5f2653c`` after filtering nonnumeric time
and missing voltage/current values:

.. list-table:: BIRDS flight measurements used by the example
   :header-rows: 1
   :widths: 18 18 24 24

   * - Satellite
     - Flight campaigns
     - Measurement times
     - Panel observations
   * - RAAVANA
     - 2
     - 2,159
     - 10,795
   * - UGUISU
     - 3
     - 3,260
     - 16,300
   * - NEPALISAT
     - 3
     - 3,040
     - 15,200
   * - TSURU
     - 40
     - 23,266
     - 116,330
   * - Total
     - 48
     - 31,725
     - 158,625

A measurement time is counted within its spacecraft and campaign; each has
five panel observations. The total therefore does not describe 158,625 unique
timestamps. TSURU's ``Test1 w batt`` and ``Test2 wo batt`` sheets are excluded
from flight analysis. The workbooks contain separate measurement sessions,
not continuous coverage between the first and last campaign dates.

Campaign dates and elapsed time
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

RAAVANA contains two campaigns, on 13 February and 11 March 2021, with 1,079
and 1,080 measurements respectively at five-second intervals. Plotting each
campaign against elapsed minutes exposes these measurements instead of
compressing them into two clusters on a month-scale date axis.

Most TSURU sheets name a month and day without a year; the last two dated
sheets explicitly name January 2022. ``campaign_year=2021`` supplies the
missing year for the earlier sheets while preserving years already present.
This is an explicit inference from the workbook sequence and TSURU's
14 March 2021 deployment, not a year provided in those sheet names. With
this choice, its 40 flight campaigns span 28 March 2021 to 24 January 2022.
Campaign dates must be sorted because workbook sheet order is not always
chronological.

.. important::

   Numeric ``Time Stamp`` values are elapsed seconds within a campaign.
   The normalized timestamp combines the campaign date at midnight with
   those elapsed seconds. Midnight is a date anchor; the workbook does not
   provide the actual UTC start time. The timezone-aware result must not
   be used as a precise UTC measurement time for orbit, Sun-position or
   eclipse alignment without an independently established start time.

The connector preserves the recorded elapsed intervals. For example, TSURU
contains intervals of 10, 10.6 and 11.3 seconds, so replacing them all with
a nominal ten-second grid would alter the source measurements.

Analysis walkthrough and attribution
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The dataset is real on-orbit telemetry from four 1U CubeSats and is published
by Jara and Lepcha (2022), DOI
`10.17632/8kp25ycf63.1 <https://data.mendeley.com/datasets/8kp25ycf63/1>`_,
under CC BY 4.0. Retain the dataset attribution when sharing derived data.
The associated article, `Jara et al. (2022)
<https://pmc.ncbi.nlm.nih.gov/articles/PMC9679683/>`_, documents the
measurement fields and collection procedure. It reports panel failures in
RAAVANA and UGUISU, but these exploratory plots do not reproduce expert
fault labels or establish a degradation rate.

See the executable :doc:`../../gallery/real_data/plot_birds_raavana_real_data`
walkthrough for the four-spacecraft overview, full-resolution RAAVANA campaign
plots, five-minute power envelopes within each campaign, and TSURU's
40-campaign history. Five-minute envelopes summarize real samples within each
session; they do not create new measurement campaigns or fill gaps.

Primary sources:

* `BIRDSOpenSource/EPS_dataset, pinned source revision
  <https://github.com/BIRDSOpenSource/EPS_dataset/tree/67ad4435c5329abde65afc16e30d725cd5f2653c>`_;
* `Mendeley dataset, version 1 and license
  <https://data.mendeley.com/datasets/8kp25ycf63/1>`_;
* `JAXA confirmation of TSURU's 14 March 2021 deployment
  <https://humans-in-space.jaxa.jp/en/biz-lab/news/detail/001359.html>`_.

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
