PV modelling and loss analytics
===============================

Explain the gap between a declared expected power and actual power, then
integrate the same comparison into an energy budget. Named stages retain
their evidence and combine into physical or operational categories. The
unexplained remainder and any gains remain visible.

Choose the baseline for the question
------------------------------------------------------------

.. list-table:: Three complete workflows
   :header-rows: 1
   :widths: 27 34 39

   * - Walkthrough
     - Expected baseline
     - What the breakdown means
   * - :doc:`Spacecraft PV loss budget </gallery/pv_analytics/plot_spacecraft_pv_loss_budget>`
     - Beginning-of-life reference power at a declared irradiance and temperature
     - A synthetic design budget through eclipse, pointing, optics, temperature,
       degradation, wiring, conversion and controller stages
   * - :doc:`Expected versus actual power </gallery/pv_analytics/plot_expected_vs_actual_power>`
     - Healthy operating power, with normal geometry and temperature already included
     - A synthetic two-array diagnostic example with supported incremental causes,
       an unexplained remainder, gains and missing observations
   * - :doc:`Flying Laptop reference gap </gallery/pv_analytics/plot_flying_laptop_reference_gap>`
     - A first-week empirical power envelope, evaluated on subsequent measurements
     - Real voltage/current telemetry with all unsupported causes kept unexplained;
       this is not an estimate of recoverable energy or physical degradation

The first two examples run offline and label their simulated observations and
assumed parameters explicitly. Flying Laptop reuses the measured-data connector
and its cached February 2018 archive; the first run downloads about 30 MB.

Install ``pip install -U "orbital-pv[examples]>=0.7.0"``. Each walkthrough includes
four figures and uses the public ``orbitalpv`` API.

Accounting contract
-------------------

For ordered cumulative powers, each contribution is the power before a stage
minus the power after it. Contributions plus the final unexplained residual
therefore equal expected minus actual power. This avoids adding overlapping
percentage losses, while making the chosen stage order explicit.

Energy summaries use a shared observation mask and a caller-selected maximum
gap. They assume linear power between accepted instantaneous samples and never
fill missing energy. Negative loss is a gain, not a value to clip away.

See :doc:`PV loss analysis </user_guide/modeling_topics/pv_loss_analysis>` for
category definitions, evidence requirements, equations and reusable API code.
