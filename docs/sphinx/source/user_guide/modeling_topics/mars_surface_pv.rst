Mars surface PV performance
===========================

``orbitalpv.mars`` connects Mars geometry, atmospheric attenuation, deposited
dust and the existing PVWatts reference adapter. It includes real InSight data
and an offline comparison. These are screening/research models; calibration
and physical limitations are exposed in outputs and examples.

Run a sol
---------

From this source checkout (the addition is not yet a PyPI release):

.. code-block:: python

   from orbitalpv import PvwattsReference, mars

   # 1 kW at AM0 reference irradiance and 25 C; scenario cell coefficient.
   reference = PvwattsReference(1000, gamma_pdc_per_c=-0.002,
                               reference_irradiance_w_m2=1361)
   profile = mars.simulate_mars_sol(
       julian_date_tt=2458449.5,  # representative date, explicitly TT
       latitude_deg=4.502,
       reference=reference,
       optical_depth=0.7,
       cell_temperature_c=-20,  # assumed CELL temperature, not air temperature
       array_dust_factor=0.8,
   )
   print(profile.attrs["energy_wh"])

``mars_solar_parameters`` implements the corrected NASA Mars24 seasonal
formulae. For civil dates, install the ``orbit`` extra and pass
``astropy.time.Time(date, scale="utc").tt.jd``. No current leap-second offset
is hard-coded in the public API. Latitude is planetographic; solar time is
local true solar time (LTST), not terrestrial clock time or mission LMST.

The sol wrapper freezes season at the supplied date, samples LTST 0--24, and
integrates across **88775.244 SI seconds**, producing Earth watt-hours per
Martian sol. It omits small within-sol seasonal/equation-of-time changes.
Output is array DC before EPS and battery losses. Existing
``orbitalpv.physics.dispatch_power`` can consume power samples and SI time for
separate storage studies.

Choose the irradiance model explicitly
--------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 22 42 36

   * - Mode
     - Calculation
     - Boundary
   * - ``lorenz_horizontal``
     - Inverse-square sunlight and solar elevation, attenuated by
       ``1 / (1 + 0.3 * tau)``; independent panel retention and temperature factors.
     - Effective irradiance proxy. Lorenz's near-normal response fit is extended
       over the day; this is not a spectral/global-irradiance solver. Horizontal only.
   * - ``components``
     - Beer-Lambert direct beam using plane-parallel airmass, supplied DHI,
       and isotropic sky/ground transposition at a fixed tilt and azimuth.
     - DHI is required. Explicit zero means a direct-only calculation, not a
       prediction that diffuse radiation vanishes on dusty Mars.

``mars_surface_power`` accepts individual LTST samples and arrays. In components
mode, azimuth is clockwise from north and tilt is 0--90 degrees. Example:

.. code-block:: python

   components = mars.mars_surface_power(
       [10, 12, 14], latitude_deg=20, declination_deg=0,
       sun_distance_au=1.52, optical_depth=0.7, reference=reference,
       cell_temperature_c=[-15, 0, -10], atmosphere="components",
       tilt_deg=20, azimuth_deg=180,
       diffuse_horizontal_w_m2=[70, 90, 70],  # explicit scenario, not observed
       ground_albedo=0.2,
   )

The Lorenz mode rejects tau above 5, nonhorizontal arrays and supplied DHI.
Its published attenuation comparison covered approximately tau 0.1--5;
0--0.1 is a transparent-limit extension. Direct-only calculations retain the
limitations of plane-parallel airmass near the horizon. Neither path models
terrain shadowing, twilight, snow/frost, anisotropic scattering or cell-resolved
spectral mismatch. Temperature coefficients and spectral factors require
appropriate calibration; terrestrial default thermal models are not imported.

Retrieve observations
---------------------

.. code-block:: python

   with mars.InSightSolarConnector(timeout_s=60) as source:
       energy = source.daily_energy(cache_path="data/raw/insight-energy.csv")
       current = source.currents(archive="0000-0099", sols=[4, 52],
                                 cache_path="data/raw/insight-0000-0099.zip")

   with mars.InSightOpacityConnector(timeout_s=60) as source:
       opacity = source.optical_depth(cache_path="data/raw/insight-tau.csv")

No key is required. Downloads verify publisher MD5 values; cache sidecars bind
request URLs and SHA-256 hashes, allowing verified offline reuse. A changed
source fails until reviewed. Provenance is in ``frame.attrs``; preserve it when
exporting (CSV does not serialize pandas attributes).

The JHU energy table contains 200 operational energy estimates; it is not a
continuous wattmeter record. The five current archives span sols 4--1369 with
large gaps. They contain two hardwired DBR string currents, not whole-array
power. Four unusable native files were found: corrupted bytes on sols 169/192
and NA placeholders on sols 916/941. Default parsing raises; explicit
``invalid_files="report"`` excludes complete invalid files and lists their
names and reasons in ``attrs["rejected_files"]``. Requested missing sols still
raise. No invented samples or byte repairs are applied.

The 758 camera opacity records are at **600 nm**, with fractional true-solar
sol, uncertainty and fit uncertainty preserved. PDS currently links the table
from a **review-directory product**. The connector labels that status and does
not assert final archive approval. There is no silent conversion to broadband
or thermal-infrared optical depth.

Evidence and reproducibility
----------------------------

.. code-block:: bash

   PYTHONPATH=src uv run python analysis/mars_surface_pv/run.py

The runner verifies pinned sources, writes the per-sol comparison and JSON
metrics, and fits only one amplitude on sols 5--39. The fixed 0.28%/sol retention
loss comes from Lorenz et al. (2020); no later energy values tune the model.
The comparison on 161 later sols has 289.5 Wh/sol RMSE (10.2% of mean energy)
and +255.0 Wh/sol bias. Geometry-only RMSE is 1327.6 Wh/sol.

Opacity is interpolated retrospectively, with a maximum 15-sol bracket and no
extrapolation. Four early sols have no supported prediction. This is a
same-mission hindcast with literature-informed parameters, not independent
validation or a future-weather forecast. Native current samples retain sleep
gaps. Source uncertainty is preserved but not yet propagated into prediction
intervals. The response scale absorbs cell temperature/spectrum/EPS effects;
it cannot be interpreted as a measured array rating.

See :doc:`/gallery/mars/plot_insight_energy`,
:doc:`/gallery/mars/plot_mars_seasons` and :doc:`/reference/mars`.
The seasonal map uses constant assumed opacity and clean panels, so it is a
scenario rather than measured global resource data.

The `Mars literature matrix <https://github.com/julianascencio/orbital-pv/blob/main/docs/literature/11_mars_surface_pv.md>`_
records the papers, implemented methods and pending spectral/climate work.
Primary foundations include `Lorenz et al. (2020) <https://doi.org/10.1029/2019EA000992>`_,
`NASA Mars24 <https://www.giss.nasa.gov/tools/mars24/help/algorithm.html>`_,
`Landis et al. (2004) <https://ntrs.nasa.gov/citations/20040191326>`_ and
`Kerr et al. (2023) <https://doi.org/10.1016/j.asr.2023.04.004>`_.
