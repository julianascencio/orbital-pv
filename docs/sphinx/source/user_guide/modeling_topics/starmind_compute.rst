SpaceX-inspired orbital compute
==============================

The Starmind example connects a news-motivated HJT manufacturing scenario to
solar generation, eclipse storage, radiative cooling and deployment throughput.
Its 175 kW average and 250 kW peak targets are SpaceX design claims. All other
hardware, orbit and launch inputs are explicit analyst assumptions.

.. image:: /_static/spacex_starmind.png
   :alt: Power, storage, thermal and launch sensitivity for Starmind-inspired scenarios
   :width: 100%

Run and inspect
---------------

Install the current source checkout, then run::

   python -m pip install -e ".[examples]"
   python analysis/spacex_starmind/run.py --output outputs/spacex_starmind
   python examples/space_business/plot_spacex_starmind.py

The runner accepts ``--input`` for a modified JSON configuration. It writes
scenario summaries, interval dispatch, beta-angle/area sensitivity, launch
sensitivity and complete input provenance. It requires no network requests.

See the :doc:`runnable gallery </gallery/space_business/plot_spacex_starmind>`
and `full analysis, evidence, equations and reference results
<https://github.com/julianascencio/orbital-pv/tree/main/analysis/spacex_starmind>`_.

What the result means
--------------------

The assumed illuminated baseline serves the full burst schedule. Reducing PV
output, entering a low-beta eclipse orbit, or reducing radiator area can make
the target infeasible. The model distinguishes continuous service from the
time-average of intermittent compute and explicitly reports platform outages
when an overloaded greedy schedule depletes storage.

Manufacturing nameplate watts use an explicitly assumed STC basis; orbital
bus power uses a separately assumed AM0 efficiency. Added usable compute is
then limited by complete-spacecraft mass and assumed launch throughput. Factory
capacity is neither deployed power nor AI workload throughput.

The thermal model uses total emitting area and a prescribed radiator temperature
with a validated EPS/storage heat allowance. It does not establish junction
temperature feasibility. The eclipse model samples fixed representative beta
angles, not an annual SSO ephemeris. No SpaceX operational performance or
deployment forecast is implied.
