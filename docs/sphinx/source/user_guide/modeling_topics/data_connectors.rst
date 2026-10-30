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
* BIRDS EPS — open panel and battery telemetry;
* Flying Laptop / DaRUS — calibrated on-orbit solar-array voltage and current;
* OPS-SAT-AD — original annotated photodiode and magnetometer measurements;
* LASP LISIRD — measured total and spectral solar irradiance;
* Earth Search Sentinel-2 — ground imagery, spectral bands and scene classification;
* OpenStreetMap / Overpass — raw solar and wind installation features.

See :doc:`ground_imagery` for image retrieval and the relationship to
Dunnett et al. (2020), including which inputs the paper actually uses.

The NOAA SWPC connector also normalizes measured GOES integral proton and
electron flux. SatNOGS metadata is public, but its telemetry endpoint currently
requires authentication; it is not an anonymous real-data example.

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

Additional measured-data workflows
----------------------------------

Install the current public API and plotting support:

.. code-block:: bash

   python -m pip install -U "orbital-pv[excel,examples]>=0.5.0"

These are separate observations with different physical meanings. An array's
electrical measurements, an irradiance instrument's input measurements, and
particle-environment measurements are not interchangeable.

.. list-table:: New executable connector examples
   :header-rows: 1
   :widths: 20 40 40

   * - Source
     - Public connector
     - Measured example
   * - Flying Laptop
     - ``FlyingLaptopConnector`` / ``fetch_flying_laptop_power``
     - :doc:`../../gallery/real_data/plot_flying_laptop_power`
   * - OPS-SAT-AD v2
     - ``OpsSatADConnector`` / ``fetch_opssat_segments``
     - :doc:`../../gallery/real_data/plot_opssat_photodiode_telemetry`
   * - TSIS-1 and SORCE TIM
     - ``LisirdConnector.total_solar_irradiance``
     - :doc:`../../gallery/real_data/plot_lisird_measured_irradiance`
   * - TSIS-1 SIM
     - ``LisirdConnector.spectral_irradiance``
     - :doc:`../../gallery/real_data/plot_lisird_measured_spectrum`
   * - NOAA GOES
     - ``NoaaSwpcConnector.goes_integral_particle_flux``
     - :doc:`../../gallery/real_data/plot_goes_measured_particle_flux`

Flying Laptop: actual array voltage and current
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The University of Stuttgart publishes monthly archives under CC BY 4.0,
`DOI 10.18419/darus-451 <https://doi.org/10.18419/darus-451>`_, with a separate
`packet and units description <https://doi.org/10.18419/darus-456>`_. The
connector reads electrical packet 4900 directly from the compressed archive,
without extracting archive paths. It validates downloads against the provider's
catalog checksum and records a SHA-256 provenance sidecar.

.. code-block:: python

   import orbitalpv as opv

   power = opv.fetch_flying_laptop_power(
       "2018-02", "data/FLP_TM_HK_2018-02.tar.bz2",
       time_min="2018-02-01", time_max="2018-02-02",
   )
   # Offline reuse of the complete downloaded month:
   month = opv.load_flying_laptop_power("data/FLP_TM_HK_2018-02.tar.bz2")

February 2018 contains 75,097 packet timestamps and 300,388 array observations.
The right, left, center and onboard experimental ``test`` array stay distinct.
Voltage is in V and current in A; ``power_w`` is calculated as V times I.
The Unix-millisecond timestamps represent UTC packet generation, with up to
400 ms difference from sensor acquisition documented by the provider. Time
filters use an inclusive start and exclusive end. The gallery shows monthly
coverage, native voltage/current/power, and daily upper envelopes.

OPS-SAT: original sensor signals and annotations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `OPSSAT-AD v2 release <https://doi.org/10.5281/zenodo.15108715>`_ supplies
303,493 original measurements in 2,123 segments from nine channels. The
connector downloads ``segments.csv`` rather than the extracted-feature table,
pins the version and SHA-256, and preserves channel, segment, expert annotation
and the provider's train/test split. The dataset is CC BY 4.0.

.. code-block:: python

   import orbitalpv as opv

   signals = opv.fetch_opssat_segments(
       "data/opssat_segments_v2.csv", channels=["CADC0892"], split="test"
   )

Photodiode and magnetometer values retain their source scale. The published
CSV supplies no engineering units, so they must not be interpreted as panel
current or generated power. The numeric ``anomaly`` field contains the expert
annotation; the inconsistent text ``label`` field is preserved but not used
for classification. The gallery plots native signals and separately selected
nominal/anomalous segments without filling the missing mission intervals.

LISIRD: measured total and spectral irradiance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`LASP's public science products <https://lasp.colorado.edu/tsis/data/>`_ supply
TSIS-1 TIM and SORCE TIM total irradiance, plus TSIS-1 SIM spectral irradiance.
The connector validates units and decodes the time conventions declared by
the LaTiS ``jsond`` metadata. Nominal bin centers and weighted average
measurement times remain separate where both are provided.

.. code-block:: python

   import orbitalpv as opv

   with opv.LisirdConnector() as connector:
       tsi = connector.total_solar_irradiance(
           "tsis_tsi_24hr", time_min="2023-01-01", time_max="2024-01-01",
           cache_path="data/tsis_2023.json",
       )
       spectrum = connector.spectral_irradiance(
           time_min="2023-06-01", time_max="2023-06-04",
           cache_path="data/tsis_spectrum_20230601_03.json",
       )

TSI fields at 1 AU and actual Earth distance are distinct and use W/m²;
spectral fields use W/m²/nm with wavelengths in nm. Provider fill values,
uncertainties, provisional flags and spectral quality bits remain explicit.
The 2023 daily series has 365 nominal bins but only 292 valid measured bins
in the checked snapshot. The example leaves the missing bins as gaps.

The spectral example uses three daily spectra with 2,104 wavelength bins
each. It shows quality-marked wavelengths separately and does not integrate
across rejected intervals. The illustrative PV response in the TSI example
is a simulation driven by measured irradiance, not measured spacecraft power.

GOES: measured particle environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import orbitalpv as opv

   with opv.NoaaSwpcConnector() as connector:
       protons = connector.goes_integral_particle_flux(
           "protons", period="7-day", cache_path="data/goes_protons.json"
       )

This retrieves a rolling observation window and caches the original response;
``refresh=True`` requests a new snapshot. Flux is in particles/(cm² s sr),
and actual satellite IDs and energy thresholds are retained. Primary proton
and electron observations can come from different GOES spacecraft. Integral
energy channels overlap and must not be summed; energetic protons can
contaminate electron measurements. These geostationary observations are
environmental context, not a spacecraft-specific radiation damage dose.

See NOAA's `proton <https://www.swpc.noaa.gov/products/goes-proton-flux>`_ and
`electron <https://www.swpc.noaa.gov/products/goes-electron-flux>`_ product
descriptions for units and limitations.

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
