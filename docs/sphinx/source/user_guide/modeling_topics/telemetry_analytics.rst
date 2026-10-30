Telemetry and Performance Analytics
===================================

The core analytics principle is to compare measured performance with expected
performance after deterministic orbital and thermal effects have been removed.

Measured power
--------------

For voltage/current telemetry:

.. math::

   P_{measured} = V I

A physics-aware residual is then:

.. math::

   r(t) = P_{measured}(t) - P_{expected}(t)

Loss accounting uses the opposite sign, so a positive value is a shortfall:

.. math::

   L(t) = P_{expected}(t) - P_{actual}(t)

``opv.power_loss_breakdown`` reconciles this gap into named, evidence-labelled
stages and reporting categories. ``opv.summarize_power_losses`` integrates
the ledger over common observed intervals and reports the uncovered portion
of each recorded time span. Gains remain negative losses and unsupported
causes remain unexplained. See :doc:`pv_loss_analysis` for the full workflow.

Case 0 baseline
---------------

Before a full orbit/attitude model is available, OrbitalPV includes a
telemetry-only baseline based on a robust upper envelope. This is useful for
testing ingestion, event plumbing, and persistent-loss detection.

The baseline deliberately does not claim physical normalization.

Health progression
------------------

The modelling hierarchy is:

1. telemetry-only upper-envelope health;
2. orbit/Sun normalized power;
3. temperature-corrected expected power;
4. radiation-aware expected power;
5. topology/EPS-aware residuals;
6. uncertainty-aware degradation and remaining-power forecasts.

The sequential PV model and loss ledger support supplied geometry, temperature,
degradation and electrical/controller states. Parameter identification, causal
diagnosis, calibrated radiation inference and uncertainty-aware forecasts are
still separate work; a loss bucket is not evidence that its physical cause has
been established.

Benchmarking
------------

Time-series evaluation should split by time and, where possible, spacecraft.
Random row splits can leak orbital cycles and make anomaly performance look
better than it is operationally.
