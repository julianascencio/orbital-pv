OrbitalPV Example Gallery
=========================

These examples are executable documentation. They use the same public API that
users receive from PyPI:

    pip install orbital-pv
    import orbitalpv as opv

Sphinx-Gallery executes the examples when the documentation site is built.
Examples remain deterministic and offline unless a page explicitly documents
a live external data source.

Featured sub-galleries
----------------------

.. toctree::
   :maxdepth: 1

   real_data/index
   space_cells/index
   constellations/index
   orbit_visualization/index

The real-data gallery retrieves and analyzes measured on-orbit spacecraft PV telemetry. The space-cell gallery compares silicon, GaAs, 3J, 4J and IMM technologies,
including temperature and radiation sensitivity. The constellation gallery
includes the Starlink Gen1 shell solar-generation simulation, while the
orbit-visualization gallery contains representative orbit families, ground
tracks, and highly elliptical orbit examples.
