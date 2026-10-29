OrbitalPV
=========

.. raw:: html

   <div style="text-align:center; margin: 1.5rem 0 2rem 0;">
     <a href="https://asvaconsulting.com">
       <img
         src="https://asvaconsulting.com/wp-content/uploads/2022/05/ASVA-1-1-scaled.jpg"
         alt="ASVA Consulting"
         style="max-width:280px; width:100%; height:auto;"
       >
     </a>
     <p style="margin-top:0.75rem;">
       <strong>Created by ASVA Consulting</strong><br>
       <a href="https://asvaconsulting.com">asvaconsulting.com</a><br>
       <a href="mailto:contacto@asvaconsulting.com">contacto@asvaconsulting.com</a>
     </p>
   </div>

**OrbitalPV** is an open-source Python research platform for spacecraft
photovoltaic performance analytics, created by **ASVA Consulting**.

It combines orbital geometry, Sun and eclipse state, spacecraft PV modelling,
space-environment context, flight telemetry, degradation analytics, and
spatiotemporal visualization.

Start here
----------

If you are new to OrbitalPV:

* read the :doc:`user_guide/getting_started/package_overview`;
* follow :doc:`user_guide/getting_started/installation`;
* run the :doc:`user_guide/getting_started/quickstart`;
* explore the :doc:`gallery/index`;
* use the :doc:`reference/index` for package and function details.

Core modelling idea
-------------------

OrbitalPV treats measured spacecraft PV power as the result of a physical and
operational chain:

.. code-block:: text

   orbit + time
       ↓
   Sun vector + distance
       ↓
   eclipse + attitude + AOI
       ↓
   AM0 effective irradiance
       ↓
   temperature + degradation
       ↓
   expected PV power
       ↓
   measured - expected
       ↓
   residual / fault / degradation analytics

Documentation structure
-----------------------

The documentation is split into a User Guide, an executable Example Gallery,
and a generated API Reference.

.. toctree::
   :maxdepth: 2
   :hidden:

   user_guide/index
   gallery/index
   reference/index
   research/index
   contributing/index
