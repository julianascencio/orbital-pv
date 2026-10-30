Ground research methods and data
================================

The public :mod:`orbitalpv.ground_research` and
:mod:`orbitalpv.ground_forecasting` modules extend the existing Sentinel-2,
OSM and GHSL workflow with explicit method provenance, geographic validation,
capacity uncertainty, dated-inventory matching and classical cloud nowcasting.
Install ``orbital-pv[ground-research,examples]`` for the complete ground workflow.
Vector inventory and EUMDAC dependencies are imported only when used.

Implementation status
---------------------

.. list-table:: What is implemented, and what remains caller-supplied
   :header-rows: 1
   :widths: 23 45 32

   * - Method or reference
     - Working implementation
     - Scientific boundary
   * - ANDPI, Zeng et al. (2025)
     - Published six-band spectral formula and histogram valley threshold,
       pinned to the authors' MIT code; prior-candidate retention is supported.
     - Whole-scene use is a standalone adaptation. Historical inventory fusion,
       the complete training/reference geography and global validation are not
       silently reproduced.
   * - Supervised segmentation
     - Balanced standardized logistic regression and the existing spectral RF;
       shared score/mask adapter and geographic holdout metrics.
     - Scores are uncalibrated. OSM supplies weak labels and missing OSM coverage
       can invalidate background-negative assumptions.
   * - PANEL (2026), TransPV (2024), PVP-Adapter (2026)
     - ``SegmentationAdapter.from_callable`` accepts an authorized local model
       runtime and records an optional local checkpoint SHA-256 and license.
     - No architecture or checkpoint is bundled. A path records provenance;
       callers load and run the original model themselves. PANEL's gated model
       terms must be accepted by the user. Do not install an unrelated package
       called ``panel`` and assume it is the remote-sensing model.
   * - Geometry and capacity
     - Polygon area/long axis; log-linear regression; separate split-conformal
       calibration and final holdout; explicit AC/DC/reported basis.
     - Row/footprint axis is not panel facing direction; no measured tilt is
       invented. Geographic shift can invalidate nominal interval coverage.
   * - Construction history
     - Overlap graph groups splits/merges, compares equal-area footprints and
       returns date brackets under explicit complete-coverage assumptions.
     - Observation/retrieval/publication dates differ. A footprint change is
       not proof of electrical commissioning.
   * - Cloud/irradiance forecasting
     - Clear-sky persistence; phase-correlation motion; local Lucas-Kanade
       optical flow; frozen-field advection; issued-weather blending.
     - Requires retrieved clear-sky index and future clear-sky GHI. Raw radiance
       is not irradiance. This is not a Baguan-solar model reproduction.

ANDPI spectral inputs
---------------------

The source formula is

.. math::

   I = \frac{B_{11} - \max(B_2,B_3,B_4,B_8,B_{12})}{B_{11}+10^{-10}}.

``andpi_index`` consumes calibrated blue, green, red, near-infrared, SWIR16 and
SWIR22 reflectance on one grid, or an existing ``PVFeatures`` object. Native
Sentinel-2 scale and offset must both be applied; dividing every source by
10,000 is not generally equivalent. The existing feature builder handles the
metadata and records 20 m SWIR interpolation to the 10 m red grid. Resampling
does not create native spatial detail. Near-zero denominators and missing data
are masked for numerical safety.

``adaptive_andpi`` follows the authors' 200-bin density histogram over [-0.5,
0.5], with peak height 2, distance 5 and prominence 0.5. ``new`` candidates use
positive peaks above 0.02, falling back to threshold 1; ``old`` candidates use
the highest two peaks, falling back to the candidate mean. Optional retention
restores a prior mask when too few of its candidates survive. The result records
which fallback and prior-mask assumptions were used. The authors' code is pinned
at ``ba2f0cd340c57c6780ed63770a9a89b855fde54b``; the MIT notice is retained in
``licenses/ANDPI-MIT.txt``.

Geographic benchmarking
-----------------------

.. code-block:: python

   from orbitalpv.ground_research import (
       benchmark_segmentation, supervised_segmentation_adapter,
   )

   model = supervised_segmentation_adapter([cestas_sample], method="logistic")
   report = benchmark_segmentation([model], [tenerife_sample])

The benchmark rejects overlapping training bounding boxes and reused site IDs
before calling the predictor. The callable receives features only. It reports
precision, recall, F1, IoU, false-positive pixels and objects, and area bias on
the exact known-label/usable-prediction support. Unknown labels do not become
negatives. Pretraining geography cannot be reconstructed from a checkpoint;
external model adapters should record known overlap or explicitly say unknown.

The reproducible cached Cestas-to-Tenerife experiment currently yields F1
0.2222 for logistic, 0.4541 for unfiltered RF, 0.0581 for fixed NDPI >= 0, and 0
for the whole-scene adaptive-ANDPI adaptation. These are weak OSM reference
agreements, not globally surveyed performance. The standalone adaptation's
failure is retained; it is not a benchmark of the paper's complete fusion.
See ``analysis/pv_mapping_generalization`` for frozen assumptions, checksums,
negative results and exports.

Capacity uncertainty and geometry
---------------------------------

``fit_geometry_capacity_model(training, calibration, ...)`` requires distinct
stable site IDs and optionally disjoint geographic groups. Area columns ending
in ``_m2`` are log transformed. The model fits only training rows and calibrates
absolute log residuals on the separate calibration table. The order statistic
is ``ceil((n + 1) * coverage)``; insufficient calibration size for a finite
interval raises an error. ``evaluate_geometry_capacity`` rejects reuse of
fitting or calibration sites/groups and reports actual coverage, MAE, RMSE,
bias, R², width and extrapolation count.

Predictions require the same polygon-area semantics used in calibration.
Extrapolation is refused unless explicitly enabled. AC/DC conversion needs an
explicit DC/AC ratio; historical ``reported`` MW cannot be relabelled AC or DC.
The converted interval does not include uncertainty in the supplied ratio.

On the bundled historical reference, fit excludes France, Canada, Italy and
Spain; France/Canada/Italy calibrate the interval and Spain tests it. The 159
Spanish sites give MAE 6.391 MW, RMSE 10.192 MW, R² 0.535 and actual coverage
77.36% for a nominal 90% interval. This below-nominal result demonstrates why
geographic transfer must be assessed explicitly. The interval omits mapping
uncertainty and cannot be advertised as guaranteed under country shift.

``summarize_pv_geometry`` measures source polygon footprints in local UTM and
retains their source attributes. Long-axis azimuth is modulo 180 degrees. A
plant boundary, row polygon and module surface are different area definitions;
none can be substituted without calibration. Actual module tilt remains
unknown unless separately measured or supplied.

Connectors and authentication
-----------------------------

.. list-table:: Original sources, access and provenance
   :header-rows: 1
   :widths: 24 41 35

   * - Public API
     - Behavior
     - Access/license boundary
   * - ``PNOAConnector``
     - Discover WMS layer names; retrieve original IGN/CNIG COG URLs; render
       explicitly labelled WMS PNG previews with WMS 1.1.1 longitude-first axes.
     - Preserve original product/date/producer attribution. Display width is
       not native resolution and WMS RGB is not calibrated reflectance.
   * - ``CopernicusDataSpaceConnector``
     - Query current ``https://stac.dataspace.copernicus.eu/v1`` with bounded,
       validated pagination; download original OData products by UUID.
     - Catalog is public. Downloads require an explicit CDSE OAuth token.
       Credentials are not persisted; S3 assets are not assumed public HTTPS.
   * - ``PVInventoryConnector`` / ``load_pv_inventory``
     - Version-pinned GRW v1.0, GM-SEUS v2.1 and ANDPI yearly release downloads;
       checksum verification and WGS84 spatial subsets of original vectors.
     - Preserve source fields and upstream terms. GM-SEUS mixes original
       CC-BY content with ODbL/noncommercial upstream records; Planet imagery
       is not redistributed with GRW. ANDPI code license is distinct from data.
   * - ``GoesABIConnector``
     - Anonymous NOAA S3 XML pagination, half-open time filtering, explicit
       satellite/product selection, bounded original netCDF downloads.
     - NOAA open data; no access token required. Retain projection, retrieval
       units, acquisition time and quality flags. S3 ETag is not SHA-256.
   * - ``EumetsatConnector``
     - Official EUMDAC Data Store search and original product streams.
     - Requires explicit user consumer key/secret or an already authorized
       store; user accepts collection-specific license. No credentials in logs
       or provenance files; no universal near-real-time access is assumed.

Downloads retain original bytes, compute SHA-256 and write a provenance sidecar.
Existing files are protected by default. Size/checksum failures leave no partial
destination. Large inventory ZIPs require explicit downloads; optional vector
dependencies read a selected member without extracting arbitrary archive paths.
GeoJSON attributes retain measured/inferred/source distinctions.

.. code-block:: python

   from orbitalpv.ground_research import (
       CopernicusDataSpaceConnector, GoesABIConnector, PVInventoryConnector,
       load_pv_inventory,
   )

   with CopernicusDataSpaceConnector() as cdse:
       scenes = cdse.search(
           bbox=(-16.45, 28.19, -16.43, 28.20),
           time_min="2026-06-01", time_max="2026-09-01", max_items=5,
       )

   # Explicit original-data transfer; inspect the source terms first.
   with PVInventoryConnector() as inventory:
       receipt = inventory.download("grw", "solar_2024q2.gpkg")
   local = load_pv_inventory("solar_2024q2.gpkg", bbox=(-17, 28, -16, 29))

   with GoesABIConnector() as goes:
       products = goes.search(
           satellite=16, product="ABI-L2-DSRF",
           time_min="2024-06-01T12:00Z", time_max="2024-06-01T13:00Z",
       )

Temporal analysis and forecast evaluation
-----------------------------------------

``match_pv_changes`` creates overlap-connected groups so a split or merge is
not automatically counted as a new installation. Unmatched objects are newly
observed/not redetected unless complete shared coverage is explicitly asserted.
Only then are added/removed dates bracketed between the two observations.
Original acquisition dates, inventory-release dates and commissioning dates
must remain distinct. Two weak maps can share systematic errors.

``forecast_irradiance`` requires dimensionless retrieved clear-sky index and
future clear-sky GHI in W/m². The default motion method is a global
phase-correlation initialization followed by local Lucas-Kanade optical flow;
``method="phase_correlation"`` selects a simpler translation baseline. Invalid
retrievals and incoming image boundaries remain masked. Frozen motion cannot
model cloud creation, dissipation or parallax. Forecast issue-time guards reject
reanalysis and weather forecasts issued after the forecast origin. Model and
reference errors are evaluated on common usable support.

The default construction and nowcasting examples are explicitly synthetic:
the repository's real cache has only one optical date per site and no independent
irradiance observations. Synthetic skill verifies algorithm behavior only.
Real evaluation needs physically retrieved satellite irradiance/cloud fields,
native resolution and DQF metadata, matching clear-sky calculations, genuinely
issued weather forecasts, and independent surface measurements.

Reproducible analyses
---------------------

* ``analysis/pv_mapping_generalization``: real cached Cestas-to-Tenerife transfer.
* ``analysis/pv_geometry_capacity``: real historical capacity and OSM geometry.
* ``analysis/pv_construction_history``: dated real inputs or explicit synthetic
  split/expansion scenario; no fabricated construction observations.
* ``analysis/satellite_irradiance_forecasting``: deterministic synthetic cloud
  transport and weather-blend scenario, with operational input APIs.

Each command writes to an empty output directory. Reports retain provenance,
reference quality, inferred/measured distinctions and important limitations.
The gallery is offline and never downloads gated models or large imagery.

Primary references
------------------

* Zeng et al., ANDPI/global PV mapping (December 2025),
  `10.1016/j.jag.2025.105005 <https://doi.org/10.1016/j.jag.2025.105005>`_.
  A 2026 press release is not the paper's publication year.
* TransPV (2024), `10.1016/j.apenergy.2023.122282 <https://doi.org/10.1016/j.apenergy.2023.122282>`_.
* PANEL (2026), `10.1016/j.isprsjprs.2026.05.012 <https://doi.org/10.1016/j.isprsjprs.2026.05.012>`_,
  `original model card <https://huggingface.co/UEXdo/PANEL>`_.
* PVP-Adapter (2026), `10.1016/j.isprsjprs.2026.07.032 <https://doi.org/10.1016/j.isprsjprs.2026.07.032>`_.
* GM-SEUS (2025 paper; 2026 data release),
  `10.1038/s41597-025-05862-4 <https://doi.org/10.1038/s41597-025-05862-4>`_.
* Global Renewables Watch (2025 preprint),
  `arXiv:2503.14860 <https://arxiv.org/abs/2503.14860>`_.
* Baguan-solar (2026 preprint),
  `arXiv:2603.14845 <https://arxiv.org/abs/2603.14845>`_.
* `PNOA imagery services <https://pnoa.ign.es/web/portal/pnoa-imagen/visualizadores-y-servicios-web>`_,
  `CDSE STAC <https://documentation.dataspace.copernicus.eu/APIs/STAC.html>`_,
  `NOAA GOES open data <https://registry.opendata.aws/noaa-goes/>`_,
  `official EUMDAC <https://gitlab.eumetsat.int/eumetlab/data-services/eumdac>`_.
