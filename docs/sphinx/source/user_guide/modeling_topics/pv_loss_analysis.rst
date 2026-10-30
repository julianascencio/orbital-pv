PV loss budgets and operating diagnostics
=========================================

OrbitalPV reconciles expected-minus-actual power into named, signed
contributions. Supply an explicit reference, a sequence of cumulative power
predictions, and actual power at the same electrical boundary. The remaining
model-minus-actual difference stays **unexplained**. A residual does not, by
itself, identify a damaged cell, a pointing error, or a radiation event.

This supports both a design budget and a comparison against telemetry. Those
analyses answer different questions, so the reference must be stated first.

Choose the reference and measurement boundary
---------------------------------------------

**Design budget.** Start with a calibrated array reference at declared
irradiance, temperature, and beginning-of-life conditions. Apply solar
resource, eclipse, incidence, optical, temperature, degradation, and electrical
effects in a stated order. Here an eclipse is a reduction relative to the
reference; it is not evidence of a spacecraft fault. An existing end-of-life
rating must not receive the same lifetime degradation a second time.

**Operating diagnostics.** Start with the output expected from a healthy
system under the conditions at each timestamp. That expectation may already
include Sun distance, eclipse, nominal pointing, cell temperature, and
scheduled operation. Add only independently supported adjustments that are
absent from this expectation. For example, a known actual pointing departure
can be compared with planned pointing. Subtracting the full eclipse or
temperature reduction again would double-count it.

The API calls the chosen starting prediction ``expected_power_w`` and the
prediction after all supplied stages ``modeled_power_w``. Record which of the
above reference definitions is being used. Both are powers in watts, not
irradiances, efficiencies, or energy totals.

Expected and actual values must describe the same panel or array, timestamp,
operating point, and measurement location. Array-terminal DC, regulator-output
DC, battery current, and payload consumption are different quantities. A
conversion-efficiency stage is appropriate only when the selected boundary
includes that converter. Spacecraft DC analysis does not need a terrestrial
AC-inverter loss unless such hardware is actually in the model.

Measured voltage times current gives **operating-point power**, which may be
below available maximum-power-point output because of a commanded limit,
shunt regulation, battery state, or load demand. NASA's Solar Maximum analysis
used peak-power-tracking operation and normalized illumination and temperature
before assessing degradation. An ISS study used shunt-current measurements to
avoid interpreting demand-limited output as array damage. [#smm]_ [#iss]_

What the categories mean
------------------------

Categories organize supplied stage contributions. They do not infer causes
or supply default percentages. Each attributed ``LossStage`` needs a
nonempty ``evidence`` description: a calibrated model, a measurement, an
operating flag, or an explicitly declared scenario assumption.

.. list-table:: Physical and operational reporting categories
   :header-rows: 1
   :widths: 18 34 48

   * - Category
     - Examples
     - Evidence needed to assign the contribution
   * - ``solar_resource``
     - Sun distance and changes in incident solar irradiance
     - Ephemeris or irradiance measurements with a stated 1-AU versus
       actual-distance convention; do not apply both corrections twice.
   * - ``geometry``
     - Earth eclipse and array incidence or pointing
     - Consistent Sun/orbit geometry, attitude, panel normals, and timing.
       A generic eclipse model does not establish self-shadowing by hardware.
   * - ``optical``
     - Coverglass transmission, contamination, spectral response
     - An applicable optical or spectral calibration, or a declared
       assumption. A broadband irradiance measurement alone cannot identify
       spectral mismatch in a multijunction device.
   * - ``temperature``
     - Change relative to the reference cell temperature
     - Cell temperature and a calibrated power-temperature relationship.
       Bus or ambient temperature is not automatically cell temperature.
   * - ``degradation``
     - Radiation retention, aging, or a verified failed string
     - Device-specific qualification, dose/fluence and shielding information,
       or independently established hardware state. A power trend alone does
       not separate these causes.
   * - ``electrical``
     - Cell/string mismatch, interconnect and wiring losses
     - Array topology, operating currents, resistance, or I-V measurements.
       Partial shading and mismatch can interact; avoid counting the same
       effect as two independent losses.
   * - ``conversion``
     - MPPT, regulator, or DC/DC conversion
     - Converter input/output measurements or an applicable efficiency model,
       plus operating mode and a matching measurement boundary.
   * - ``operations``
     - Commanded limits, shunting, clipping, disconnected hardware
     - Relevant controller state, limits, or availability flags. These may
       represent intended operation rather than hardware underperformance.
   * - ``unexplained``
     - Final model-minus-actual residual
     - Reserved for the remainder. It can contain omitted physics, model
       calibration error, sensor error, timing error, or unobserved operations.

NASA identifies radiation, optical darkening, contamination, and mechanical
or electrical failures among spacecraft-array degradation mechanisms. [#nasa]_
Array mismatch is also coupled to irradiance, temperature, and wiring; a
single combined I-V operating point need not realize every cell or string's
individual maximum power. [#mismatch]_

The terrestrial PVWatts system-loss defaults are not spacecraft defaults.
Its documentation also explicitly excludes temperature and inverter effects
from generic losses when those effects are already calculated elsewhere.
That same accounting rule applies here. [#pvwatts]_

Use cumulative stages, not independent percentages
--------------------------------------------------

For a starting power :math:`P_0`, supplied cumulative predictions
:math:`P_1,\ldots,P_n`, and actual power :math:`P_a`, the ledger is

.. math::

   L_k = P_{k-1} - P_k, \qquad
   L_{\mathrm{unexplained}} = P_n - P_a,

.. math::

   P_0 - P_a = \sum_{k=1}^{n} L_k + L_{\mathrm{unexplained}}.

``LossStage.power_column`` contains the power **after** the stage, not the
stage's loss in watts. Stages use the order supplied by the caller. Category
totals combine these contributions without reordering them.

For example, two successive 10% reductions take 100 W to 90 W and then 81 W.
Their contributions are 10 W and 9 W, totaling 19 W. Independently subtracting
10 W twice would be incorrect. The attribution depends on order even when
the final product does not. During full eclipse, applying eclipse first
leaves zero power for later incidence or temperature reductions.

An independent "remove one effect" sensitivity can still be useful, but
its individual differences generally do not add to the total. Report such a
sensitivity separately; it is not an additive loss budget. With nonlinear
models, recompute each cumulative prediction, including coupled effects,
rather than treating every mechanism as a constant multiplier.

Gains remain signed. Improved incidence, a cooler array, or measured output
above expectation can give a negative contribution. The library does not
clip these to zero or rescale contributions to make them sum to 100%.

Generate a physical design sequence
---------------------------------------

``opv.pvwatts_loss_chain`` produces cumulative design predictions using the
existing calibrated space PVWatts model. For example, the following inputs
are explicit illustrative assumptions, not measurements:

.. code-block:: python

   import orbitalpv as opv

   reference = opv.PvwattsReference(pdc0_w=100.0, gamma_pdc_per_c=-0.003)
   chain = opv.pvwatts_loss_chain(
       reference,
       illumination_fraction=[1.0, 0.5, 0.0],
       cosine_aoi=0.9,
       cell_temperature_c=[25.0, 45.0, 35.0],
       degradation_factor=0.97,
       wiring_efficiency=0.99,
   )

The returned sequence starts at ``reference_power_w`` and exposes named
``after_..._w`` columns through irradiance, eclipse, pointing, spectral and
optical adjustments, temperature, degradation, mismatch, wiring, conversion,
clipping, and availability. ``modeled_power_w`` also includes the supplied
curtailment factor. Select cumulative columns as ``LossStage`` inputs when
building the ledger.

The array reference already contains its calibrated cell efficiency and
beginning-of-life optical performance. ``optical_factor`` describes an
additional change relative to that reference; do not multiply by the cell's
conversion efficiency or nominal coverglass transmission again. Unity
defaults mean that an effect has not been added to this scenario, not that
flight evidence proves the effect absent. The helper is an engineering power
model, not a detailed multijunction or radiation-damage calculation.

Build a breakdown
-----------------

The input should already contain aligned powers. In this example the
starting expectation includes nominal geometry and temperature, while two
additional, independently supplied stages represent actual pointing and
controller operation:

.. code-block:: python

   import orbitalpv as opv

   stages = (
       opv.LossStage(
           name="pointing",
           power_column="after_actual_pointing_w",
           category="geometry",
           evidence="Timestamp-aligned calibrated attitude solution",
       ),
       opv.LossStage(
           name="controller_limit",
           power_column="after_controller_limit_w",
           category="operations",
           evidence="Regulator mode and commanded power-limit telemetry",
       ),
   )
   breakdown = opv.power_loss_breakdown(
       frame,
       stages,
       expected_power_column="healthy_expected_w",
       actual_power_column="measured_array_power_w",
       group_columns=("panel_id",),
   )

   print(breakdown.samples)
   print(breakdown.components_w)
   print(breakdown.categories_w)

``samples`` contains the canonical expected, modeled, and actual powers,
signed total, attributed, and unexplained losses, group identifiers, and
``valid``. ``components_w`` and ``categories_w`` share its index. Keep these
frames together and treat them as read-only results.

With no stages, the entire expected-minus-actual gap remains unexplained:

.. code-block:: python

   comparison = opv.power_loss_breakdown(
       frame,
       expected_power_column="reference_power_w",
       actual_power_column="measured_power_w",
       group_columns=("panel_id",),
   )

This is also the honest representation when a telemetry-only empirical
reference is available but attitude, temperature, or controller state is not.
State how the reference was fitted and selected; a high quantile of telemetry
does not establish the array's physical maximum power or isolate degradation.

Integrate energy without inventing missing observations
-------------------------------------------------------

.. code-block:: python

   summary = opv.summarize_power_losses(breakdown, max_gap_s=90.0)
   print(summary.totals)
   print(summary.components)
   print(summary.categories)

The cutoff is an explicit analysis choice, in seconds. Set it using the source
cadence and event timescales. A large cutoff does not make intervening power
known. The summary assumes instantaneous power varies linearly between
accepted endpoints; it is not an integrator for interval-average or cumulative
energy telemetry. These sampling conventions require different treatment,
as described in RdTools' power-to-energy documentation. [#rdtools]_

An interval contributes only when both endpoints are valid for **every**
required power and the time separation is no greater than ``max_gap_s``.
NaNs stay in place as interval boundaries. No energy is interpolated across
excluded gaps or extrapolated before the first or after the last sample.
All ledger terms use this same support, so their signed watt-hour totals
reconcile with the expected-minus-actual energy gap.

The summaries report:

* Expected, modeled, and actual energy in Wh, and signed total, attributed,
  and unexplained energy differences.
* Gross positive gap and surplus energy. Linear segments are split at their
  zero crossings before these two areas are integrated.
* Per-stage and per-category ``net_loss_wh``, nonnegative ``loss_wh`` and
  ``gain_wh``, plus signed ``percent_expected``.
* Valid sample and interval counts, observed duration, the recorded
  first-to-last window, and its coverage fraction.

``percent_expected`` uses expected energy over the same accepted intervals,
not an unweighted average of per-sample ratios. It is undefined when expected
energy is zero. Energy results are NaN when there are no usable intervals.
Coverage describes each group's recorded window; it does not include an
unobserved period outside that window.

The signed contributions add to the total gap, but the sum of their gross
positive parts need not equal the gross total shortfall: simultaneous gains
and losses can cancel between components. Likewise, adding panel energies
with different coverage is not a full-fleet energy estimate over a common
mission window. Inspect coverage per panel before aggregating it.

Telemetry checks and interpretation
-----------------------------------

* Align timestamps and averaging conventions before creating the input
  frame. The library converts timestamps to UTC and assumes naive values
  are UTC; it cannot determine a logger's unknown time zone or packet delay.
* Preserve panel, spacecraft, and segment identity through ``group_columns``.
  Duplicate timestamps within a group are rejected. Resolve retransmissions
  or repeated segment times explicitly rather than silently averaging them.
* Convert source fill values and invalid quality flags to NaN. Expected and
  stage predictions must be nonnegative; actual signed power is retained,
  including small negative sensor offsets. Calibration and quality screening
  remain the caller's responsibility.
* Check synchronization around eclipse edges and mode changes. Timing error
  can produce adjacent positive and negative residuals without any change
  in hardware performance.
* Evaluate residuals against model and measurement uncertainty. A positive
  unexplained contribution is a discrepancy to investigate, not a confirmed
  failure or a unique physical diagnosis.

Gallery examples
----------------

* :doc:`Physical design waterfall </gallery/pv_analytics/plot_spacecraft_pv_loss_budget>`:
  follow the array reference through physical and operational stages.
* :doc:`Expected versus actual operating power </gallery/pv_analytics/plot_expected_vs_actual_power>`:
  compare explicitly synthetic telemetry with known control states and
  preserve gains, residuals, and observation gaps.
* :doc:`Measured Flying Laptop reference gap </gallery/pv_analytics/plot_flying_laptop_reference_gap>`:
  keep a measured empirical-reference gap unattributed when the available
  evidence cannot identify its physical causes.

Together they show how the available evidence determines the detail of a
defensible breakdown.

References
----------

.. [#nasa] NASA, *State-of-the-Art of Small Spacecraft Technology*, Power:
   https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/

.. [#smm] NASA-TM-86194, *Solar maximum: Solar array degradation*:
   https://ntrs.nasa.gov/citations/19850025862

.. [#iss] NASA Glenn, *International Space Station Solar Array Wing
   On-Orbit Electrical Performance Degradation Measured*:
   https://ntrs.nasa.gov/citations/20050215410

.. [#mismatch] Sandia PV Performance Modeling Collaborative, *DC Array IV*:
   https://pvpmc.sandia.gov/modeling-guide/3-dc-array-iv/

.. [#pvwatts] PVWatts, *System Losses*:
   https://pvwatts.nlr.gov/docs/help_system_sysloss.php

.. [#rdtools] RdTools, *energy_from_power*:
   https://rdtools.readthedocs.io/en/stable/generated/rdtools.normalization.energy_from_power.html
