# Chronological flight power uncertainty

This offline analysis consumes a checksum-verified subset of **real Flying
Laptop packet-4900 measurements**. It compares persistence, an explicitly
assumed seasonal lag, and multivariate ridge regression. A separate subsequent
calibration partition supplies joint voltage/current block-conformal bounds;
power bounds are extrema of the product rectangle, so `P = V × I` remains
coherent even for signed telemetry.

```bash
python analysis/flight_power_uncertainty/run.py
```

The outputs are `summary.json` and timestamped `predictions.csv` under
`outputs/flight_power_uncertainty`. The committed `reference_results.json`
records a reproducible run. The accompanying gallery executes the same public
methods on the same native measurement snapshot.

The three UTC days are disjoint fit, calibration and evaluation periods.
Windows whose future target crosses a partition boundary are purged. Windows
crossing a cadence discontinuity are excluded, with no interpolation. The
three forecast horizons are 1, 4 and 10 source samples at nominal 30.15 s.
The 180-sample seasonal comparator is an empirical 90.45-minute lag, **not a
mission-validated orbital period**.

These are forecasts of **observed operating power**. They are not a healthy
reference, available MPP, recoverable energy loss, physical fault diagnosis,
or mission-wide validation. Chronological calibration does not make real
time-series blocks exchangeable; report measured interval coverage and width.

References: FLP Team, [telemetry](https://doi.org/10.18419/darus-451),
[packet definitions](https://doi.org/10.18419/darus-456), CC BY 4.0.
The block-envelope direction is motivated by [Task-aware conformal power
envelopes for multi-horizon spacecraft monitoring (2026)](https://doi.org/10.1371/journal.pone.0360910).
This transparent baseline does not claim to reproduce its complete method.
