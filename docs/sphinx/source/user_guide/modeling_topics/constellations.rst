Imaging and space-computing constellations
===============================================================================

The constellation gallery connects mission geometry with viewing conditions,
Earth eclipses, and illustrative spacecraft solar generation. All examples
consume the public ``orbitalpv`` API and run offline.

.. code-block:: bash

   python -m pip install -U "orbital-pv[examples]>=0.6.0"

Earth observation and surface irradiance
-------------------------------------------------------------------------------

Geostationary weather imagers observe reflected sunlight and thermal radiance.
Retrieval systems combine these observations with atmospheric information to
estimate cloud properties and solar irradiance reaching Earth's surface.
The satellite's own array power is a separate quantity.

The :doc:`../../gallery/constellations/plot_geo_irradiance_imaging_constellation`
example uses a selected five-spacecraft network. Its inputs are a frozen
nominal-slot snapshot checked on 30 October 2026:

.. list-table:: Selected GEO imagers
   :header-rows: 1
   :widths: 25 25 20 30

   * - Spacecraft
     - Nominal longitude
     - Imager
     - Selected role
   * - GOES-18
     - 137.0 degrees W
     - ABI
     - Western Americas / Pacific
   * - GOES-19
     - 75.2 degrees W
     - ABI
     - Eastern Americas / Atlantic
   * - Meteosat-12
     - 0 degrees
     - FCI
     - Europe / Africa full disk
   * - Meteosat-9
     - 45.5 degrees E
     - SEVIRI
     - Indian Ocean coverage
   * - Himawari-9
     - 140.7 degrees E
     - AHI
     - East Asia / western Pacific

The example shows each orbital slot, geometric overlap at a stated 10-degree
minimum ground elevation, daily array-power profiles, and GEO eclipse seasons.
The viewing map is a spherical-Earth geometry calculation. Instrument scan
limits, daylight, clouds and retrieval-quality masks must be applied separately
before claiming imagery or irradiance-product availability.

The :doc:`../../gallery/constellations/plot_polar_earth_observation_constellation`
example follows the nominal Sentinel-2B/2C design: 786 km mean altitude,
98.62-degree inclination, 10:30 descending mean local solar time, and 180-degree
phasing in a shared plane. It shows the 3D pair, one-day subpoint tracks,
ground daylight, spacecraft illumination, and per-spacecraft PV profiles.
Sentinel-2's reflected-light imagery provides surface context; this example
does not derive a surface-irradiance product or predict operational revisit.

Nominal slots and designed phase offsets make these examples reproducible.
They do not identify where an actual spacecraft was at a particular UTC epoch.
All electrical reference powers, temperatures and optical factors are stated
assumptions rather than mission hardware specifications.

Proposed space data-center orbits
-------------------------------------------------------------------------------

The :doc:`../../gallery/constellations/plot_space_data_center_orbits`
example compares two published altitude choices and a local-time control:

.. list-table:: Published parameters and example assumptions
   :header-rows: 1
   :widths: 25 35 40

   * - Scenario
     - Source-backed input
     - Explicit example assumption
   * - Suncatcher-motivated
     - Google illustrates a 650 km compact cluster and a dawn-dusk SSO concept.
     - 06:00 ascending mean local solar time; first-order J2 inclination.
   * - ASCEND-motivated
     - The completed study considers 1,400 km SSO and 800 kW compute blocks.
     - 06:00 ascending mean local solar time; crossing time is unspecified by the source.
   * - Imaging-style control
     - No named mission is represented.
     - 650 km, 10:30 descending; same altitude as the first case isolates crossing time.

Google's October 2026 hardware-prototype announcement is distinct from its
proposed computing constellation. ASCEND is a completed feasibility study,
not an operating constellation. These examples do not forecast deployment
dates or claim commercial or environmental viability.

The annual calculation uses a 365.2422-day circular Earth orbit, fixed
23.43928-degree obliquity and 1 AU solar distance. The node advances with the
mean Sun while the physical Sun's declination changes. The resulting beta
angle drives the cylindrical-shadow eclipse estimate.

.. important::

   Dawn-dusk SSO does not imply continuous full sunlight. In this model the
   650 km dawn case reaches about 19.7 minutes of eclipse per orbit in its
   least favorable season. At 1,400 km the point-Sun model gives zero eclipse,
   but the clearance is only about 0.048 degrees, smaller than the solar disc.
   The separate finite-Sun calculation therefore shows partial occultation.

The example translates the finite-Sun profile into a declared power budget:
800 kW compute load, 20% overhead, a 1.5 MW beginning-of-life array reference,
45-degree C cells, 0.96 optical factor, 95% charging/discharging efficiencies,
and 80% usable battery depth. It checks both the eclipse energy deficit and
whether the array can replenish it before the next orbit. Battery capacity
alone cannot fix an orbit-average energy shortfall. Reported capacity values
are one-eclipse lower bounds, not complete battery or thermal designs.

Compact clusters and distributed fleets
-------------------------------------------------------------------------------

The :doc:`../../gallery/constellations/plot_compact_data_center_constellation`
example uses the Suncatcher paper's illustrative 81-node count, 650 km altitude
and 1 km cluster radius. A centroid approximation gives all compact nodes the
same Earth-shadow history; the local layout is a static illustration without
formation-flight or collision-control dynamics.

A separately labeled hypothetical 81-node ring spreads the same nodes around
one orbital plane. Its summed solar generation is smoother, but each node
still enters Earth's shadow. The example compares the sum of local energy
deficits with a deficit calculated after aggregating fleet power. They differ
because an arithmetic fleet sum does not transfer electrical power between
spacecraft. The ring is a comparison scenario, not Google's proposed layout.

Reusable public geometry helpers
-------------------------------------------------------------------------------

.. code-block:: python

   import orbitalpv as opv

   altitude_m = 650_000.0
   period_s = opv.circular_orbit_period_s(altitude_m)
   inclination_deg = opv.sun_synchronous_inclination_deg(altitude_m)
   raan_deg = opv.raan_from_local_solar_time_deg(
       6.0, sun_right_ascension_deg=0.0, ascending=True
   )
   eclipse_s = opv.circular_eclipse_duration_s(altitude_m, beta_angle_deg=58.6)

``sun_synchronous_inclination_deg`` matches first-order J2 nodal precession
to the mean annual solar motion. It is a design estimate and omits drag,
higher gravity harmonics and short-period perturbations.

For the crossing-time helper, the mean Sun's right ascension corresponds to
mean local solar time; physical solar right ascension corresponds to apparent
solar time. The distinction matters away from the chosen idealized epoch.

``circular_eclipse_duration_s`` uses a point Sun and cylindrical Earth shadow.
``earth_occultation_fraction`` resolves the finite Earth/Sun discs, including
penumbra. Both assume a spherical Earth; operational work needs traceable
ephemerides, frames, actual attitude and validated system parameters.

Primary references
-------------------------------------------------------------------------------

* `NOAA operational GOES status <https://ospo.noaa.gov/operations/goes/status.html>`_
  and `ABI downward-shortwave retrieval metadata
  <https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc%3AC01524/html>`_.
* `EUMETSAT Meteosat series <https://www.eumetsat.int/our-satellites/meteosat-series>`_
  and `MSG service geometry <https://www.eumetsat.int/msg-services>`_.
* `JMA Himawari overview <https://www.jma.go.jp/jma/jma-eng/satellite/>`_.
* `Copernicus Sentinel-2 mission parameters <https://sentiwiki.copernicus.eu/web/s2-mission>`_
  and `products <https://sentiwiki.copernicus.eu/web/s2-products>`_.
* `Google Suncatcher design paper
  <https://services.google.com/fh/files/misc/suncatcher_paper.pdf>`_
  and `October 2026 prototype update
  <https://blog.google/innovation-and-ai/models-and-research/google-research/project-suncatcher-prototype/>`_.
* `ASCEND architecture study <https://ascend-horizon.eu/activities/>`_
  and `European Commission project status <https://cordis.europa.eu/project/id/101082517>`_.
* `NASA spacecraft thermal-environment course, eclipse geometry slides 110-119
  <https://ntrs.nasa.gov/api/citations/20200007746/downloads/20200007746.pdf>`_
  and `ESA discussion of J2 perturbations
  <https://gssc.esa.int/navipedia/index.php?title=Perturbed_Motion>`_.
