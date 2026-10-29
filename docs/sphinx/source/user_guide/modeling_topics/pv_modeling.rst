Space PV Modelling
==================

OrbitalPV reuses tested photovoltaic equations from pvlib where their physical
assumptions remain useful, while keeping spacecraft-specific inputs outside
terrestrial modelling abstractions.

Reference model
---------------

The first reference layer uses a calibrated PVWatts-style DC model. The
reference power is defined at an explicit irradiance and temperature rather
than silently assuming terrestrial STC is the spacecraft design point.

Effective irradiance
--------------------

The initial broadband model is:

.. math::

   G_{eff} = G_{AM0} f_{eclipse} f_{AOI} f_{spectral} f_{optical}

where each factor is supplied by a separate physical or calibration layer.

Single-diode modelling
---------------------

The De Soto/single-diode adapter is useful for silicon and other
single-junction experiments, parameter-estimation tests, and validation.

It should not be interpreted as a native III-V multijunction model.

Multijunction roadmap
---------------------

A future III-V model should preserve junction-specific spectral response and
series current matching. The target chain is:

.. code-block:: text

   AM0 spectrum
       ↓
   spectral response per junction
       ↓
   junction photocurrent
       ↓
   current matching + tunnel junctions
       ↓
   cell I-V
       ↓
   string / array topology
