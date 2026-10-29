Orbit and Sun Geometry
======================

Spacecraft PV performance begins with geometry. OrbitalPV keeps propagation,
reference frames, Sun position, eclipse state, and panel incidence separate so
that each step can be validated independently.

Propagation engines
-------------------

For public Earth-orbit catalog objects, the default path is Skyfield with the
Vallado SGP4 implementation. New catalog ingestion should prefer CCSDS OMM
records where available.

For missions that publish SPICE kernels, SpiceyPy provides the higher-fidelity
path for ephemeris, frames, clocks, and attitude products.

Sun geometry
------------

The core geometry state is the spacecraft-to-Sun vector:

.. math::

   \\mathbf{s} = \\mathbf{r}_{sun} - \\mathbf{r}_{sc}

The incidence factor for a panel normal :math:`\\mathbf{n}` is initially
represented by:

.. math::

   f_{AOI} = \\max(\\hat{\\mathbf{n}} \\cdot \\hat{\\mathbf{s}}, 0)

Eclipse
-------

OrbitalPV includes an Earth-disc/Sun-disc occultation calculation that returns
a continuous illumination fraction between 0 and 1. This supports sunlight,
penumbra, and umbra rather than reducing eclipse to a Boolean too early.

Frame discipline
----------------

Do not store an inertial vector as longitude/latitude geometry. Scientific
states must retain their frame and epoch. Earth-fixed GIS products are derived
later for visualization and spatial queries.

Visualization examples
----------------------

The Example Gallery includes several offline orbit visualizations:

* :doc:`../../gallery/orbit_visualization/plot_orbit_families_3d` compares
  representative LEO, polar/SSO-like, MEO, and GEO circular orbits around Earth.
* :doc:`../../gallery/orbit_visualization/plot_molniya_orbit_3d` shows a
  representative highly elliptical Molniya-style orbit.
* :doc:`../../gallery/orbit_visualization/plot_ground_track` transforms an
  inclined inertial orbit into an Earth-fixed ground track and handles the
  antimeridian discontinuity.

These examples use deterministic geometry for documentation. Operational
analysis should use traceable orbital elements or mission ephemerides.

Constellation-scale example
---------------------------

The Example Gallery also includes a constellation-scale demonstration:

* :doc:`../../gallery/constellations/plot_starlink_gen1_solar_generation`
  models the FCC-authorized 1,584-spacecraft, 550 km, 53° Starlink Gen1 shell
  and computes fleet illumination and illustrative solar generation over one orbit.

The orbital geometry follows the public FCC authorization. Electrical power
assumptions in the example are explicitly illustrative rather than manufacturer
specifications.
