Flight calibration, energy budgets and uncertainty
==================================================

This workstream connects measured electrical channels, chronological operating
forecasts and explicit uncertainty. It adds a pinned BUPT-1 source, reusable
linear/Bayesian calibration, causal multivariate lag baselines, joint V/I
block-conformal envelopes and measured energy reconciliation. These are
transparent research baselines with reproducible examples, not flight-qualified
models or full reproductions of the referenced papers.

Measurement, expectation and forecast
-------------------------------------

Keep three different questions explicit:

.. list-table:: Different model purposes
   :header-rows: 1
   :widths: 24 46 30

   * - Quantity
     - Question
     - Required evidence
   * - Measured operating power
     - What voltage times current was observed at this boundary?
     - Channel units, clocks and electrical boundary
   * - Healthy expected power
     - What would an independently specified healthy system produce?
     - Health evidence, operating constraints and appropriate physics
   * - Operating forecast
     - What measured voltage/current is likely to follow this history?
     - Causal inputs and chronological validation

An autoregressive operating forecast can learn persistent underperformance.
It therefore cannot automatically serve as a healthy reference for the
:doc:`pv_loss_analysis` ledger. ``fit_linear_calibration`` and
``fit_bayesian_linear_calibration`` require an explicit ``purpose``. The
``healthy_reference`` option also requires a description of independent
health evidence. This declaration documents intent; it cannot verify the
truth of caller-supplied evidence.

BUPT-1 / SatelliteCOTS connector
--------------------------------

The authors' public repository supplies platform telemetry from BUPT-1, a
12U CubeSat carrying Atlas 200 DK and Raspberry Pi 4B computing payloads.
OrbitalPV pins the following original files to commit
``951b41521351d535b7c2354916d9c4991602e8c7`` and verifies their SHA-256 values:

* ``CommonData-Telemetries/telemetry_all.csv.zip``: approximately 81 MB,
  separate MPPT1/2 and battery1/2 channels.
* ``Energy-ShortTerm/telemetries/all.csv``: group-multiplexed short-term data.

.. code-block:: python

   import orbitalpv as opv

   archive = "/tmp/orbitalpv-bupt1/telemetry_all.csv.zip"
   with opv.SatelliteCOTSConnector(timeout_s=120) as connector:
       connector.download(archive)

   frame = opv.load_bupt1_telemetry(
       archive,
       time_min="2023-05-05 09:00:00",
       time_max="2023-05-05 15:00:00",
   )

The source has no explicit redistribution licence, so raw BUPT-1 files are
downloaded into the caller's cache rather than bundled in the repository.
The connector supports offline checksum verification and streaming reads of
the ZIP member, without extracting archive paths to disk. Its raw provenance
records the pinned commit, source URL, hash and retrieval time.

The source clock has no published timezone declaration in the checked schema.
The default loader preserves naive source-local times. Relative elapsed-time
energy accounting remains possible; absolute orbit/event alignment requires a
separately established timezone. Supply ``source_timezone`` to convert that
caller-established timezone to UTC, and then supply aware time bounds. The
loader never silently assumes UTC.

Voltage is normalized from mV to V and current from mA to A. The result keeps:

* ``pv_input_power_w``: sum of observed MPPT input voltage times input current;
* ``solar_bus_power_w``: observed MPPT output currents times the observed bus
  voltage, following the authors' calculation;
* ``bus_power_w``: observed total voltage times total current;
* ``battery_source_signed_power_w``: source-signed battery V times I;
* separate branch currents, component temperatures and original clocks/rows.

These quantities do not establish unconstrained maximum-power availability.
They also do not establish that every multiplexed sensor was sampled at the
same physical instant. Common-file rows preserve the publisher's alignment.
The short-term group-multiplexed normalizer exposes group-specific powers and
does not invent a simultaneous aggregate. Zero temperature values, signed
sensor offsets and duplicate clocks remain visible.

Measured energy reconciliation
--------------------------------

.. code-block:: python

   budget = opv.measured_energy_budget(
       frame,
       battery_column="battery_source_signed_power_w",
       battery_discharge_sign=-1,
       max_gap_s=2,
   )
   print(budget.summary)

The sign above follows the original authors' plotting convention. Verify it
before applying the same assumption to other hardware or channels.
``measured_energy_budget`` integrates trapezoids only where all supplied
channels have finite endpoint values and the interval is shorter than the
declared maximum gap. It rejects duplicate or unsorted clocks. All terms use
the same accepted intervals:

.. math::

   E_{residual} = E_{solar,bus} + E_{battery,discharge} - E_{load,bus}.

The residual remains unexplained. It can include sensor timing, calibration,
unobserved electrical branches and boundary mismatch, so it is not automatically
a physical conversion loss. The returned interval table and summary expose
accepted duration, excluded intervals and coverage. Coverage is telemetry
coverage, not spacecraft availability.

The reproducible six-hour BUPT-1 analysis reports 21,598 native records from
09:00 to 15:00 in the source-local clock on 5 May 2023. Median cadence is one
second; two-second intervals are accepted by the declared integration cutoff.
Over 5.99972 observed hours, solar bus energy is 113.200 Wh, battery
discharge under the source convention is 27.871 Wh, and bus-load energy is
104.597 Wh. The remaining balance is +36.474 Wh. Separately observed PV-side
input energy is 129.783 Wh; its difference from bus output is not assigned
to a specific loss cause. The analysis also estimates compute-load power from
measured branch currents and explicitly stated nominal rails, distinguishing
that estimate from independently measured branch power. Nonzero computing
currents occur in 7,349 records; the nominal-rail compute-energy estimate is
22.580 Wh. The sizable positive balance is retained as a limitation of the
channel alignment/boundary interpretation, not presented as energy creation.

See :doc:`/gallery/flight_research/plot_bupt1_energy_budget` and
``analysis/bupt1_energy_budget``. The offline gallery uses explicitly labelled
precomputed measured aggregates, while the analysis reproduces them from the
pinned download.

Linear calibration and the Gaussian posterior
---------------------------------------------

The deterministic model uses training-only feature means/scales and an
unpenalized intercept. An optional ridge penalty operates in standardized
feature coordinates. The Bayesian alternative uses a normal coefficient prior
and a known, caller-supplied Gaussian observation noise:

.. math::

   y = X\theta + \epsilon,\qquad
   \epsilon \sim \mathcal{N}(0,\sigma^2 I),\qquad
   \theta \sim \mathcal{N}(0,\tau^2 I),

.. math::

   \Sigma = (X^T X/\sigma^2 + I/\tau^2)^{-1},\qquad
   \mu = \Sigma X^T y/\sigma^2.

The implementation uses linear solves. Predictive variance is
``x @ covariance @ x + noise_variance``; latent-mean variance excludes the
noise term. Noise/prior values must come from training data or independent
evidence. Missing physics, non-Gaussian noise and future regime changes are not
covered merely by drawing a Gaussian interval.

Timestamped predictions are checked against the last training label. Omitting
timestamps permits in-sample algebraic inspection; evaluations should supply
them. See :doc:`/gallery/flight_research/plot_bayesian_reference_calibration`
for a clearly labelled synthetic healthy-reference experiment.

Causal multi-horizon forecasting
--------------------------------

``make_lagged_vi_data`` constructs features using only origin/past samples and
targets using positive future horizons. It checks the declared native cadence
over each complete lag/target span. It neither fills gaps nor changes sampling
frequency. Features can include additional measured variables, provided they
were available at the prediction origin.

``chronological_forecast_split`` places training, calibration and evaluation
into separate clock intervals. A window is discarded when any of its future
labels crosses the training or calibration boundary. Historical lag values can
precede a partition boundary because they were already observable.

Three baselines are available:

* ``persistence_vi_forecast`` repeats the last observed V/I;
* ``seasonal_lag_vi_forecast`` uses explicit earlier lag values; a sample lag is
  not a mission-validated orbital period;
* ``fit_linear_vi_forecaster`` fits a direct multivariate, multi-horizon ridge
  model and keeps the latest training label in its provenance.

Forecast arrays have axes ``sample, horizon, (voltage, current)``. Their power
forecast is always the product of their V and I forecast. These baselines do
not assert physical healthy operation, infer faults or recover attitude.

Joint V/I conformal envelopes
-----------------------------

``calibrate_block_conformal_vi`` freezes residual scales selected on training
data or independent evidence. A calibration score is the maximum normalized
absolute residual across voltage, current, all horizons and every sample in a
nonoverlapping block of consecutive records. An incomplete trailing block is
excluded from scores, while its target times remain inside the embargo.

For ``n`` calibration blocks and requested coverage ``c``, the quantile is the
``ceil((n + 1) * c)`` order statistic. If that rank exceeds ``n``, it returns
infinity rather than claiming an unsupported finite interval.

The V/I bounds define a rectangle. Power bounds are the minimum and maximum
of its four corner products, which remains correct when intervals include
negative signed sensor values. No independently predicted power band can
contradict the corresponding V/I band.

Finite-sample conformal coverage requires exchangeable calibration/test block
scores. Real spacecraft time series, overlapping forecast targets, eclipse
transitions and operating-mode changes can violate that assumption. A
chronological split does not prove independence. Report empirical simultaneous
coverage and interval width on untouched later observations.

Real-data benchmark and current limitation
------------------------------------------

The Flying Laptop example uses 8,599 actual right-array V/I pairs across
1-3 February 2018, with a CC BY 4.0 snapshot and SHA-256 provenance. It assigns
one UTC day each to fit, calibration and evaluation. Its long seasonal lag
requires continuous source windows, leaving 1,395 training, 1,533 calibration
and 1,578 evaluation windows; the exclusions are reported.

At approximately 30 s, persistence has 1.91 W power MAE and ridge has 2.12 W.
At approximately five minutes, ridge has 7.08 W MAE and persistence has
10.61 W. No claim is made that the more complex baseline wins at every horizon.

The global block-conformal envelope is currently very conservative: joint
power coverage is approximately 99.87%, but mean derived power interval width
is approximately 575 W. **Those broad bounds are not useful control precision.**
They are retained visibly as a baseline limitation, motivating better
operating-state features and validated conditional calibration. No evaluation
measurements are used to fit coefficients or residual scales.

See :doc:`/gallery/flight_research/plot_flying_laptop_intervals` and
``analysis/flight_power_uncertainty/reference_results.json`` for the full
metrics and provenance. The snapshot predicts measured operating power, not
available array MPP or causal loss categories.

Primary sources
---------------

* SatelliteCOTS / MobiCom 2024: `Deciphering the Enigma of Satellite Computing
  with COTS Devices: Measurement and Analysis <https://arxiv.org/abs/2401.03435>`_
  and `pinned source repository
  <https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS/tree/951b41521351d535b7c2354916d9c4991602e8c7>`_.
* `Task-aware conformal power envelopes for multi-horizon spacecraft
  monitoring (2026) <https://doi.org/10.1371/journal.pone.0360910>`_. The
  OrbitalPV implementation is a simpler baseline, not the paper's full method.
* FLP Team: `Flying Laptop telemetry <https://doi.org/10.18419/darus-451>`_
  and `telemetry packet definitions <https://doi.org/10.18419/darus-456>`_,
  CC BY 4.0.
