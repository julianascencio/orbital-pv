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

Case 0 baseline
---------------

Before a full orbit/attitude model is available, OrbitalPV includes a
telemetry-only baseline based on a robust upper envelope. This is useful for
testing ingestion, event plumbing, and persistent-loss detection.

The baseline deliberately does not claim physical normalization.

Health progression
------------------

The planned hierarchy is:

1. telemetry-only upper-envelope health;
2. orbit/Sun normalized power;
3. temperature-corrected expected power;
4. radiation-aware expected power;
5. topology/EPS-aware residuals;
6. uncertainty-aware degradation and remaining-power forecasts.

Benchmarking
------------

Time-series evaluation should split by time and, where possible, spacecraft.
Random row splits can leak orbital cycles and make anomaly performance look
better than it is operationally.
