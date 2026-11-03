Lunar surface PV, storage and mobility
========================================

``orbitalpv.lunar`` connects lunar terrain, solar geometry, photovoltaic output,
panel temperature, battery dispatch and rover movement. It reuses the existing
SPICE engine, calibrated PVWatts reference, thermal balance and battery model.
The six gallery examples run offline from source-checked inputs.

Inputs and evidence
---------------------

.. list-table:: Public sources and their interpretation
   :header-rows: 1
   :widths: 22 38 40

   * - Connector
     - Inputs
     - Evidence boundary
   * - ``LolaConnector``
     - PGDA polar 80 m DEM; 5 m DEMs and height-error maps for Sites 01, 04, 11.
     - Laser-altimetry-derived, interpolated terrain. Pixel spacing is not the
       effective measurement resolution. Missing heights are retained.
   * - ``DivinerConnector``
     - PDS4 seasonal polar cumulative temperature tables and XML labels.
     - Binned bolometric brightness measurements from 2009--2020; the supported
       family covers L_s 0--60 degrees and 24 subsolar-longitude bins. Not a
       dated future temperature forecast or measured cell temperature.
   * - ``LunarSpiceConnector``
     - DE421 planetary SPK, lunar orientation PCK, frame kernel and leap seconds.
     - Computed Sun/Earth vectors in MOON_ME_DE421, consistent with the terrain.
       The downloader never changes the global SPICE kernel pool.
   * - ``LunarIlluminationConnector``
     - NASA SVS 4930 metadata, reference images and explicitly selected frames.
     - Qualitative rendered references. Pixel brightness is not irradiance and
       these images are not used as numerical validation targets.

All four use anonymous HTTPS, bounded downloads, retrieval times and SHA256
receipts. Cached files are checked against the requested product and checksum;
corrupt or mismatched caches raise errors. Provider errors do not produce
synthetic fallback data. No additional account connector is needed.

The data preparation script retains original XML and verbatim Diviner subset
rows. It records original and derived hashes, extraction rules and geometry
settings in ``examples/lunar/_data/provenance.json``. The checked-in bundle is
about 5 MB; refreshing its originals downloads roughly 550 MB once.

Methods
---------

Terrain and sunlight
~~~~~~~~~~~~~~~~~~~~~~

Positions use planetocentric latitude, east-positive longitude and elevations
above the 1,737,400 m lunar sphere. Polar stereographic axes use a south-pole
origin and longitude-zero central meridian. The raster reader rejects Earth
CRSs, alternate scale parameters and unsupported calibration offsets.

``terrain_horizon`` transforms grid centres to Cartesian lunar coordinates and
then to the observer's true east/north/up basis. It finds the maximum elevation
angle in each azimuth sector, including lunar curvature and tower height.
Three terrain layers cover nearby 5 m detail, a 40 km-wide 80 m window and a
broad 1280 m sampled grid. Their observer elevation is held consistent; coarse
inner samples are excluded where finer data is available.

This is a sampled sector-envelope model. It can overestimate shading within a
sector and miss subpixel peaks; it does not interpolate a continuous surface
along every ray. Finite map extent, DEM interpolation and layer disagreements
remain limitations. Missing sectors raise errors. Published height-error maps
can be downloaded, but their correlated uncertainty is **not** propagated into
confidence intervals in this version.

``lunar_ephemeris`` requires explicitly loaded kernels and propagates coverage
errors. It uses simultaneous geometric vectors, without light-time corrections.
``lunar_solar_geometry`` adds topocentric azimuth/elevation, inverse-square solar
flux and spherical-Earth eclipse visibility. Earth's atmosphere is omitted.

``solar_disc_visibility`` integrates a uniform solar disc above a locally
straight horizon. Limb darkening and variation across the disc are omitted.
Terrain and Earth visibility fractions are multiplied; simultaneous overlap
is approximate. Solar incidence uses the disc centre.

PV and thermal balance
~~~~~~~~~~~~~~~~~~~~~~~~

``lunar_pv_power`` supports fixed orientation, azimuth tracking at a fixed tilt,
and ideal two-axis Sun tracking. The explicit AM0 reference feeds the existing
PVWatts equation. There is no atmospheric diffuse component. Ground reflection,
mutual array shading, tracker electricity and dust deposition are not implicit;
optical retention is a caller-supplied scenario.

The yield/storage examples assume 28% reference efficiency, -0.2%/K relative
temperature coefficient, one square metre and constant 25 C cells. These are
illustrative hardware parameters, not measurements for a particular cell.

``lunar_panel_thermal`` separately solves the existing transient radiative and
conductive energy balance. The ground view factor is averaged over all emitting
faces and the sky contribution is reduced accordingly. For Diviner bolometric
brightness temperatures, use ``ground_emissivity=1``: radiance already encodes
emissivity. Physical ground temperatures instead require their emissivity.
Incoming ground IR is thermal forcing, never photovoltaic irradiance.

The thermal example uses nearby measured spatial temperature percentiles as
three **constant boundary scenarios**. It does not reconstruct time histories
from spatial samples. These boundaries drive July 2026 modelled sunlight.
Efficiency's linear temperature approximation remains a screening model.

Storage, tower design and rover routing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``size_lunar_storage`` enumerates array areas and nominal battery capacities,
reusing energy-conserving dispatch with charge/discharge power limits, losses
and SOC bounds. A feasible candidate must serve the load and, by default, end
with at least its initial SOC. Initial stored energy cannot silently compensate
for an undersized energy supply. Capacity and efficiency are constant; there is
no chemistry-specific cold-temperature or ageing model.

The example uses a continuous 1 kW payload plus 103 W heating. Heater demand
comes from an explicitly assumed equivalent thermal conductance (not lunar
convection): ``max(UA*(Tset-Tsink)-internal_heat, 0)``. The separate panel model
does not model a lander's enclosure temperature.

The tower analysis compares the lowest feasible candidate mass at each tested
height, using 3 kg/m² panels, 150 Wh/kg storage and an assumed tower mass of
20 kg + 5 kg/metre. This excludes many balance-of-system components and is not
a structural design or continuous global optimum.

``energy_aware_route`` searches a time-expanded four-neighbour grid, including
waiting. It respects slope, speed, charge/discharge power and energy reserve,
with rolling resistance, ascent, housekeeping and heaters. Generation and heat
loads are averaged over edge endpoints and assumed constant over each step.
The highest-energy state at each cell/time dominates lower-energy states. The
objective is earliest feasible arrival, then highest remaining energy. Terrain
below grid resolution, wheel slip, navigation and communication constraints
are outside scope. All rover parameters in the example are scenarios.

Run and reproduce
-------------------

From a source checkout of this change:

.. code-block:: bash

   python -m pip install -e ".[examples,ground,orbit]"
   python analysis/lunar_surface_pv/run.py --output outputs/lunar_surface_pv
   python examples/lunar/plot_lunar_terrain_yield.py
   python examples/lunar/plot_lunar_tower_orientation.py
   python examples/lunar/plot_lunar_storage_survival.py
   python examples/lunar/plot_lunar_thermal_diviner.py
   python examples/lunar/plot_lunar_rover_route.py
   python examples/lunar/plot_lunar_data_sources.py

No network is needed for these commands after installation. Figures appear
interactively; use ``MPLBACKEND=Agg`` for headless execution. The analysis runner
writes numerical CSV/JSON outputs. Optional original-data regeneration:

.. code-block:: bash

   python analysis/lunar_surface_pv/fetch_inputs.py --cache /path/to/lunar-cache

Default analysis inputs include a full 2026 year at two-hour boundaries and
July 1--31 at half-hour boundaries. Energy/storage uses left-endpoint constant
power; the thermal solver uses right-endpoint constant forcing and 300 s
substeps. Darkness durations are censored by the time window. One year does not
cover the approximately 18.6-year lunar precession cycle. The runner exports a
July time/azimuth-resolution sensitivity comparison; it is not an uncertainty
distribution or proof of convergence at all sites/seasons.

For the supplied Site01 July case, changing sector width from 4 to 1 degrees
at a half-hour time step changes modelled 30-day yield from about 222 to
231 kWh/m² and longest darkness from 49.5 to 29.5 hours. This substantial
sensitivity is why the coarse screening outputs must not be treated as precise
storage requirements. The 2-degree default is documented rather than presented
as a converged high-resolution ray-tracing solution.

Tests cover geometric axes, spherical horizons, monotonic height response,
finite-disc limits, Earth occultation, thermal equilibrium and energy closure,
storage terminal SOC, rover reserve/detours/obstacles, PDS labels and cache
integrity. These establish implementation checks, **not validation against
measured lunar PV output**.

References
------------

* `NASA PGDA large-area LOLA products <https://pgda.gsfc.nasa.gov/products/90>`_
  and `5 m site maps and uncertainties <https://pgda.gsfc.nasa.gov/products/78>`_.
* Gläser et al. (2014), *Illumination conditions at the lunar south pole using
  high resolution Digital Terrain Models from LOLA*,
  `doi:10.1016/j.icarus.2014.08.013 <https://doi.org/10.1016/j.icarus.2014.08.013>`_.
* Ross et al. (2023), *Preliminary quantification of the available solar power
  near the lunar South Pole*,
  `doi:10.1016/j.actaastro.2023.06.040 <https://doi.org/10.1016/j.actaastro.2023.06.040>`_.
* Schorghofer and Williams (2020), *Mapping of Ice Storage Processes on the
  Moon with Time-dependent Temperatures*,
  `doi:10.3847/PSJ/abb6ff <https://doi.org/10.3847/PSJ/abb6ff>`_.
* `Diviner data and citations <https://www.diviner.ucla.edu/data>`_;
  `PDS archive <https://pds-geosciences.wustl.edu/missions/lro/diviner.htm>`_.
* `NAIF lunar frame specification <https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf>`_.
* `NASA SVS 4930, Ernie Wright <https://svs.gsfc.nasa.gov/4930/>`_.
* Dhere and Santiago (1993), *Computation of photovoltaic parameters under
  lunar temperature variation*,
  `NASA NTRS 19940006939 <https://ntrs.nasa.gov/citations/19940006939>`_.

The cited studies motivate these experiments; their numerical results are not
claimed to have been independently reproduced here.
