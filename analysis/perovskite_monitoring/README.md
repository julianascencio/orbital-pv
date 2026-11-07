# Perovskite flight monitoring: cadence versus evidence

**Customer and decision.** A smallsat payload operator and its solar-cell supplier
(e.g. the Science Tokyo/EneCoat/JAXA demonstration team) must allocate scarce
matched I–V sweep and downlink opportunities before using flight evidence in a
follow-on array procurement decision. Compare daily versus weekly valid sweeps
and 28, 91, 182, 364 or 728 days of monitoring. The KPI is the smallest constant
annual power loss detectable with 80% probability using a two-sided 95% interval.
The illustrative decision target is 5%/year, not a mission requirement supplied
by JAXA. Business value is an explicit evidence/acquisition trade: avoid paying
for more sweeps when calibration stability or elapsed time limits the result.
No dollar savings, qualification approval or supplier lifetime is inferred.

## News and evidence audit — retrieved November 7, 2026

[JAXA's announcement](https://www.ihub-tansa.jaxa.jp/english/topics_Origamisat2_en.html)
is dated **October 30, 2026 (updated)**, eight days before this review. It reports
I–V measurements beginning May 30 and satellite-bus power delivery on
**September 10, 2026**; these event dates are distinct from the page date. The
page identifies future long-term degradation monitoring as the next activity.
It supplies no numerical I–V time series or sensor uncertainty. We import **no
flight measurements** and reproduce no copyrighted images or article passages.
The event is reported flight evidence; all numerical campaign inputs are
**modeled analyst assumptions**. This is a new planning case motivated by the
news, not a measurement of that satellite.

The broader scan also considered:

- [NASA's November 5 final IROSA installation](https://www.nasa.gov/blogs/spacestation/2026/11/05/spacewalkers-install-final-roll-out-solar-array/): event and publication on November 5. Orbital operations/array augmentation already addressed by merged PR #32.
- [Astrolab's November 4 LUMIS announcement](https://www.astrolab.space/2026/11/04/astrolab-unveils-lumis-power-and-communications-node-for-lunar-operations/): proposed lunar utility design already addressed by merged PR #34.
- [JPL's October 26 Mars dust report](https://www.jpl.nasa.gov/news/nasas-perseverance-offers-clues-to-protect-crews-from-mars-dust/): observations over 1,645 sols, with paper publication announced for October 27; spacesuit dust measurements are not PV degradation telemetry.
- [JAXA SSPS research](https://www.ard.jaxa.jp/eng/research/ssps/ssps.html): background on space-based solar power, not a dated new commercial-delivery result.

Repository review found no open PRs; recent merged work included #31 tandem
procurement, #32 firm power, #34 lunar service and #35 license packaging. Existing
`estimate_degradation` is a telemetry-envelope heuristic; it does not design
campaigns with known covariance or a bounded calibration drift. Radiation and
recovery remain possible physical mechanisms, **not causes attributed by this
statistical model**.

## Inputs, method, and uncertainty

`examples/space_business/_data/monitoring_noise_cases.csv` is an original scenario
table loaded through the existing free-access `orbitalpv.data.load_table` CSV
connector. No new mission connector is justified without public numeric data.
The paired provenance JSON records source URLs, retrieval date and rights; the
runner writes the input checksum. Dependencies are NumPy, pandas and Matplotlib,
already in the workspace. No new runtime dependencies or online requests.

For each matched device, let `y = ln(P_MPP / P_expected)` after externally validated
illumination, temperature, spectral and electrical-boundary normalization. Use
`y = a + b*t + error`, with time in Julian years (365.25 elapsed days). The public
`orbitalpv.analytics` methods build log-power covariance, plan campaigns, and fit
positive normalized power when qualified measurements become available.

- Baseline: independent log noise sigma 0.02 (approximately 2% relative noise).
- Correlated sensitivity: add sigma 0.03 exponential noise, time constant 7 days:
  `C_ij = 0.02² delta_ij + 0.03² exp(-abs(day_i-day_j)/7)`.
- Drift sensitivity: unknown linear calibration slope bounded by ±0.01/year in
  natural-log power. It is a bound, not an independent sample error or a Gaussian
  standard deviation. Constant gain is absorbed by the intercept.

Generalized least squares uses `V = inverse(X.T @ inverse(C) @ X)`. The slope
standard error is `sqrt(V[1,1])`. The implementation solves systems rather than
forming `inverse(C)`. The drift-expanded slope interval is
`b_hat ± (z_0.975 * SE + d)`. A loss is detected when its upper endpoint is below
zero. To attain 80% detection at the worst opposing drift, the true log-loss
magnitude must reach `(z_0.975 + z_0.8)*SE + 2*d`. The second drift term accounts
for the actual opposing drift; omitting it would overstate statistical power.
Annual fractional loss is `1-exp(-magnitude)` (not simply slope × 100).

[NIST weighted regression](https://www.itl.nist.gov/div898/handbook/pmd/section1/pmd143.htm)
provides the inverse-variance regression basis; this implementation extends the
weight matrix to declared full covariance. [Sandia's PV degradation guide](https://pvpmc.sandia.gov/tools/pv-degradation-methods/)
motivates normalization and distinguishing methods. These terrestrial-method
references do not validate a space perovskite noise model. The Gaussian detection
threshold above is derived from the stated model, not copied flight performance.

## Executed findings

Minimum detectable annual loss (95% interval, 80% worst-drift detection):

| Duration | Noise case | Daily sweeps | Weekly sweeps |
|---|---|---:|---:|
| 364 days | Independent | 1.01% | 2.59% |
| 364 days | Correlated | 5.39% | 6.02% |
| 364 days | Correlated + drift | 7.26% | 7.88% |
| 728 days | Correlated + drift | 3.93% | 4.16% |

The one-year weekly plan uses 53 valid sweeps versus 365 daily. Under correlation,
this 6.89× acquisition increase improves the threshold by only 0.63 percentage
points. With drift, neither one-year plan meets the illustrative 5% target.
Extending weekly monitoring to 728 days needs 105 sweeps and reaches 4.16% under
the assumed stationary model. This points to longer monitoring and better
calibration characterization before increasing cadence. It does **not** establish
728 days as the minimum duration or an optimal operational schedule.

The short-campaign annual rates extrapolate a constant log slope and can be very
large. They express poor detection capability, not a physical lifetime forecast.
Noise covariance must be validated from independent calibration or replicates;
uncertainty in that covariance is not included. No flight data, measured degradation,
synthetic flight observations, or modeled economics are represented as measurements.
Seasonal/attitude bias, hysteresis, radiation/thermal recovery, nonlinear aging,
unknown drift beyond the bound, missing sweeps and different sweep directions can
invalidate the inference. MPP-normalized data are required: load-limited bus
power is not a substitute. Statistical detection is not a procurement acceptance
test; absence of detected loss does not prove stability.

## Reproduce and validate

From the repository root (Python 3.13+):

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 MPLBACKEND=Agg uv run python analysis/perovskite_monitoring/run.py
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 MPLBACKEND=Agg uv run python examples/space_business/plot_perovskite_monitoring.py
uv run pytest tests/test_monitoring.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
MPLBACKEND=Agg uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

The runner produces 30 rows in `outputs/perovskite_monitoring/campaigns.csv`, a
`campaigns.png` figure, `summary.json`, and checksum-bearing `input_manifest.json`.
`reference_results.json` records the executed long-campaign values. The automatic
Sphinx gallery registers `examples/space_business/plot_perovskite_monitoring.py`;
the research index links it and the analytics reference documents the API.

Tests check the closed-form independent-noise solution, exact exponential trend
recovery, gain/time-origin invariance, correlated/drift sensitivity and rejected
invalid inputs. A seeded 20,000-realization synthetic-noise experiment verifies
80% detection and the nominal false-positive tail with worst-case opposing drift.
This is statistical verification, not flight validation. Repository CI also
runs web checks, wheel builds, strict gallery builds and license-package checks.
