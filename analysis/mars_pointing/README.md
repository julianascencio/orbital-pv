# Mars orbital array pointing reserve

NASA published its [ESCAPADE powered Earth flyby update](https://science.nasa.gov/science-research/heliophysics/nasas-escapade-completes-powered-earth-flybys-now-en-route-to-mars/) on **November 9, 2026**. The reported flybys occurred **November 7 and 9**; Mars arrivals on **September 7 and 9, 2027** and science beginning June 2028 are future plans. This case was selected November 10 (one-day-old news).

The customer is a Mars mission power/attitude planning team, motivated by ESCAPADE's campaign. The decision is whether a proposed 30° array off-pointing allowance retains a 20% power reserve, or whether to reduce the angle, shed load or increase array rating. This is an illustrative reusable planning screen, not a change recommendation for ESCAPADE's actual hardware. Its fixed-array geometry, bus loads, losses and retained power have not been calibrated to mission telemetry.

## Scope and evidence

The repository already covers surface Mars dust/atmosphere, lunar utility service, ISS augmentation/storage, cell procurement, radiation/EOL, orbital compute, deployment evidence and SBSP delivery. No open PR overlapped this case at selection. The distinct contribution is a seasonal, **sunlit orbital pointing constraint**, reusing existing solar geometry and inverse-square methods.

The recent-news review also included NASA's November 5 [final iROSA installation](https://www.nasa.gov/blogs/spacestation/2026/11/05/spacewalkers-install-final-roll-out-solar-array/); that overlaps the existing augmentation case. Existing merged deployment, perovskite and SBSP studies cover the other reviewed array/cell and orbital-power themes. No new radiation degradation measurements are inferred from the ESCAPADE report.

Sources were retrieved November 10, 2026. [NASA Mars24](https://www.giss.nasa.gov/tools/mars24/help/algorithm.html), updated January 7, 2025, supplies the published analytical distance approximation (B1, D2). The implementation reuses `orbitalpv.mars.mars_solar_parameters`; generated distances are **modeled**, not measured or a downloaded spacecraft trajectory. No new connector is needed. Repeated attempts to obtain JPL Horizons vectors returned date-only records; those incomplete responses are not inputs. Existing repository functionality provides a reproducible offline alternative with an explicit lower-fidelity boundary.

The checked-in configuration and all engineering inputs are **author-selected scenarios** under the repository license. Only URLs, factual metadata and original model outputs are included; NASA articles, imagery and software binaries are not redistributed. See `examples/space_business/_data/mars_pointing_provenance.json` for dates, units, rights and evidence labels.

## Method and constraints

For Sun–Mars distance `r` in AU, available normal-incidence bus power is
`P0 = P_1AU × retention × bus_efficiency / r²`.
The existing `am0_irradiance` supplies the inverse-square factor. At angle θ,
`P_bus = P0 cos(θ)`. Required power is `load × (1 + reserve_fraction)`.
The new public `orbitalpv.physics.pointing_power_envelope` returns the maximum
angle `acos(required/P0)` in degrees, feasibility and headroom in W. If normal
incidence is infeasible, the angle is NaN. Positive reserve is relative to load,
not generated power; it is not a statistical confidence bound.

The base case assumes 1,400 W array rating at 1 AU and reference temperature,
90% retained output, 90% conversion efficiency, 300 W continuous bus load,
20% reserve and 30° off-pointing. TT calendar dates run September 1, 2027 through
September 1, 2029 inclusive at one-day sampling. TT labels are not UTC. This
window covers a seasonal planning campaign around the announced arrival, not
an asserted spacecraft trajectory or actual operations schedule.

## Executed results

| Modeled KPI | Result |
| --- | ---: |
| Sun–Mars distance | 1.38136–1.66598 AU |
| Required bus power including reserve | 360 W |
| Worst sampled date (TT) | 2029-01-20 |
| Minimum headroom at 30° | −6.163 W |
| Daily samples failing reserve at 30° | 108 / 732 |
| Tightest feasible off-pointing angle | 28.223° |
| Minimum 1 AU rating for 30°, sampled window | 1,424.385 W |
| Increase over assumed rating | 1.742% |
| Fixed 1.52367934 AU baseline headroom | +63.016 W |
| Naïve fixed-1-AU baseline headroom | +622.073 W |

All base-case normal-incidence samples remain feasible. A constant 1.52367934 AU baseline (the Mars24 distance prefactor) also misses
the seasonal reserve failure, despite including the average distance reduction.
The failing 30° samples
still supply the assumed 300 W load: the failure is of the **reserve criterion**,
not a modeled loss of service. Counts are sampled seasonal feasibility, not
outage durations, duty cycles or delivered energy.

The 36-case sensitivity varies rating (1,000/1,200/1,400/1,600 W), retained
power (80/90/100%) and load (250/300/350 W); 12 combinations pass every sample.
A separately assumed +0.1% distance stress raises required rating to
1,427.235 W. That stress is not a validated Mars24 error bound. Retention is a
static aggregate multiplier, not an estimated radiation degradation curve.

Business value is an explicit requirement trade: compare array procurement and
mass cost with pointing restrictions or load scheduling before committing a
power budget. No actual spacecraft bill of materials, savings or revenue is
available, so no dollar ROI is claimed. The computed minimum is a threshold,
not a recommended qualified design margin.

Limitations: Mars-center geometry approximates an orbiter's solar distance;
it cannot describe cruise. No eclipses, battery discharge/recharge, array
shadowing, thermal dependence, spectral response, voltage constraints, slew
dynamics, instrument pointing, aging chronology or flight qualification are
modeled. Daily samples can miss extrema. A flight decision needs actual
spacecraft ephemerides, telemetry, load timelines and coupled EPS/thermal models.

## Reproduction

Python 3.13+, uv, workspace numpy/pandas and lab matplotlib; pyarrow for analysis
outputs. No credentials, paid services or live network are required after setup.

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_mars_pointing.py
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/mars_pointing/run.py
uv run pytest tests/test_pointing_power.py tests/test_examples_public_api.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

The analysis writes `outputs/mars_pointing/{config.json,input_manifest.json,
metrics.json,logs.jsonl,events.parquet,seasonal_power.csv,sensitivity.csv}` and
`figures/pointing.png`. The manifest records SHA-256 hashes of configuration,
provenance, example and physics sources. The runnable gallery entry is
`examples/space_business/plot_mars_pointing.py`, discovered by Sphinx Gallery and
linked from the research index. Tests exercise analytic thresholds, impossible
states, reserve semantics, units/bounds, monotonicity and the sizing identity.
