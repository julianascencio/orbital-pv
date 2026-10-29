.. _quickstart:

Quickstart
==========

Install OrbitalPV and import its public API:

.. code-block:: bash

   python -m pip install orbital-pv

.. code-block:: python

   import orbitalpv as opv

   g_am0 = opv.am0_irradiance(opv.ASTRONOMICAL_UNIT_M)
   g_effective = opv.effective_irradiance_w_m2(
       g_am0,
       illumination_fraction=1.0,
       cosine_aoi=0.85,
       optical_factor=0.96,
   )

   reference = opv.PvwattsReference(
       pdc0_w=30.0,
       gamma_pdc_per_c=-0.002,
   )

   expected_power_w = opv.pvwatts_dc_space(
       g_effective,
       cell_temperature_c=45.0,
       reference=reference,
   )

Orbit geometry
--------------

Generate a representative circular LEO directly from the public package:

.. code-block:: python

   positions_m = opv.circular_orbit_positions_m(
       altitude_m=550_000.0,
       inclination_deg=51.6,
       samples=721,
   )

Telemetry baseline
------------------

.. code-block:: python

   telemetry = opv.make_demo_telemetry(seed=42)
   normalized = opv.add_robust_baseline(opv.add_power(telemetry))
   health = opv.daily_health(normalized)

Next steps
----------

* :doc:`../modeling_topics/orbit_sun_geometry`
* :doc:`../modeling_topics/pv_modeling`
* :doc:`../modeling_topics/telemetry_analytics`
* :doc:`../../gallery/index`
