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
