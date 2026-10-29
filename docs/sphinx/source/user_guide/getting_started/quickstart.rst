.. _quickstart:

Quickstart
==========

This short example computes AM0 irradiance, applies illumination and incidence
geometry, and evaluates a calibrated PV reference model.

.. code-block:: python

   from space_pv_pvmodel import (
       PvwattsReference,
       effective_irradiance_w_m2,
       pvwatts_dc_space,
   )
   from space_pv_space_env import am0_irradiance

   one_au_m = 149_597_870_700.0
   g_am0 = am0_irradiance(one_au_m)
   g_effective = effective_irradiance_w_m2(
       g_am0,
       illumination_fraction=1.0,
       cosine_aoi=0.85,
       optical_factor=0.96,
   )

   reference = PvwattsReference(
       pdc0_w=30.0,
       gamma_pdc_per_c=-0.002,
   )

   expected_power_w = pvwatts_dc_space(
       g_effective,
       cell_temperature_c=45.0,
       reference=reference,
   )

The result is an engineering reference calculation. It is not yet a complete
III-V multijunction, radiation-degraded spacecraft-array model.

Telemetry baseline
------------------

A deterministic synthetic dataset is available for validating the analytics
pipeline:

.. code-block:: bash

   uv run --package space-pv-cli space-pv case0 --demo

Next steps
----------

* :doc:`../modeling_topics/orbit_sun_geometry`
* :doc:`../modeling_topics/pv_modeling`
* :doc:`../modeling_topics/telemetry_analytics`
* :ref:`sphx_glr_gallery`
