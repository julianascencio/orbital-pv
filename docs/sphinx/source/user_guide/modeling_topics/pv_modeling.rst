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

Sequential power and loss stages
------------------------------------------------------------

``opv.pvwatts_loss_chain`` exposes the individual cumulative powers behind a
PVWatts-based reference prediction, then adds optional degradation, mismatch,
harness, conversion and controller factors. It returns each stage in watts
and preserves temperature or irradiance gains relative to the reference.

The factors describe independently measured states or explicit assumptions;
they are not inferred from low power. Inherent cell and coverglass efficiencies
already included in the calibrated reference must not be applied twice.

Combine these predictions with ``opv.power_loss_breakdown`` and
``opv.summarize_power_losses`` to obtain signed power contributions and an
energy waterfall. See :doc:`pv_loss_analysis` and the
:doc:`PV-analytics gallery </gallery/pv_analytics/index>` for complete examples.

Single-diode modelling
----------------------

The De Soto/single-diode adapter is useful for silicon and other
single-junction experiments, parameter-estimation tests, and validation.

It should not be interpreted as a native III-V multijunction model.

Space cell technology simulator
-------------------------------

OrbitalPV 0.4 adds an empirical AM0 cell simulator for technology comparison
and early mission/system studies. It exposes five built-in reference
technologies:

==============================  =========  ===========
Technology                      Junctions  AM0 baseline
==============================  =========  ===========
Crystalline silicon             1          16.8 %
Single-junction GaAs            1          19.0 %
InGaP/GaAs/Ge triple-junction   3          29.5 %
Four-junction III-V             4          31.5 %
Inverted metamorphic (IMM)      4          32.0 %
==============================  =========  ===========

The silicon, 3J, 4J and IMM electrical reference points are anchored to the
NASA Small Spacecraft Technology State-of-the-Art power-system survey. The
single-junction GaAs baseline follows NASA heritage AM0 values and published
GaAs voltage/efficiency ranges.

The model reproduces reference Voc, Vmp, Jsc and Jmp with an empirical I-V
shape and then applies:

* irradiance scaling from the AM0 reference;
* logarithmic irradiance dependence of voltage;
* technology-specific temperature coefficients;
* a configurable 1-MeV-electron-equivalent radiation retention factor.

Example:

.. code-block:: python

   import orbitalpv as opv

   result = opv.simulate_space_cell(
       "triple_junction",
       irradiance_w_m2=1361.0,
       cell_temperature_c=80.0,
       fluence_1mev_e_cm2=5e14,
   )

   print(result.vmp_v, result.pmp_w_m2, result.efficiency)

The built-in radiation-retention values are deliberately broad comparison
assumptions. They are not qualification data for a specific commercial cell.
For flight design, create a custom orbitalpv.SpaceCellTechnology using
manufacturer or campaign-specific radiation/temperature measurements.

NASA references
---------------

NASA Small Spacecraft Power Subsystems:
https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/

NASA Solar Power Technologies for Future Planetary Science Missions:
https://science.nasa.gov/wp-content/uploads/2023/09/Solar_Power_Tech_Report_FINAL.pdf

Junction-resolved roadmap
-------------------------

The empirical simulator is intentionally a system-level layer. A higher
fidelity multijunction model should preserve junction-specific spectral
response and series current matching:

.. code-block:: text

   AM0 spectrum
       ↓
   spectral response per junction
       ↓
   junction photocurrent
       ↓
   current matching + tunnel junctions
       ↓
   junction-resolved I-V
       ↓
   string / array topology

This is the next fidelity step for detailed materials and radiation studies.
