Space Environment and Degradation
=================================

Radiation degradation is not represented as one fixed percentage per year in
the long-term architecture.

The intended modelling chain is:

.. code-block:: text

   trajectory
       ↓
   particle environment
       ↓
   energy-resolved flux / fluence
       ↓
   shielding / coverglass
       ↓
   NIEL / DDD / equivalent fluence
       ↓
   electrical parameter degradation
       ↓
   retained array power

Current implementation
----------------------

The current ``space-pv-space-env`` package provides AM0 irradiance scaling and
incidence helpers. Radiation integration is a roadmap feature.

Planned environment sources include IRENE/AE9/AP9/SPM, NOAA space-weather
products, and mission-specific environment models.

Combined stressors
------------------

Radiation is only one source of change. Thermal cycling, UV exposure, atomic
oxygen, contamination, micrometeoroids, interconnect fatigue, and EPS mode
changes can all affect measured power.

For this reason, degradation analytics should estimate state and uncertainty
rather than automatically attribute every long-term loss to radiation.
