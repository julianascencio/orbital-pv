# Repaired solar panel: retain or collect more evidence?

ESA published its [Da Vinci panel testing report](https://education.esa.int/da-vinci-satellite-team-assesses-solar-panel-performance-at-esa-estec/) on **November 5, 2026**. Tests took place in **early September 2026**, with no exact day given. This study selected that nine-day-old publication on **November 14, 2026**. The report describes TU Delft's damaged and repaired CubeSat panel, AM0 simulator measurements and imaging; it supplies **no numerical power readings**. No measured or advertised performance is substituted for missing data.

The customer is a CubeSat electrical test lead facing the same retain-versus-replace decision. The decision here is narrower: does the electrical evidence justify retaining the panel under a predeclared minimum power-retention requirement, or is more evidence needed before committing to replacement? The baseline accepts a point estimate above 95%; the alternative requires a one-sided 95% lower bound above 95%. Both percentages are **study assumptions, not ESA requirements**. Constraints are matched AM0 spectrum, irradiance, temperature and maximum-power electrical boundary, a known uncertainty budget, and independent paired repeat errors for one panel. The technical KPIs are retained Pmax and its lower bound. Business value is directing limited test effort toward calibration evidence when extra flashes cannot resolve the decision, avoiding unsupported acceptance or premature replacement. No vendor costs, schedule savings or avoided losses are claimed.

## Selection and nonduplication

Reviewed main `7c2b1a6`, architecture, existing connectors, methods, analyses, gallery and recent commits. There were no open PRs at selection. Existing cases cover degradation monitoring, deployment trial reliability, ISS augmentation, Mars pointing, lunar utility/distribution, SBSP delivery and orbital AI power. This contribution addresses paired **electrical retention acceptance**, distinct from time-trend detection or deployment success probabilities. `orbitalpv.data.load_table` already supplies the needed CSV ingestion; no new connector or dependency is warranted.

The November 14 primary-source review included these adjacent topics; they are context, not additional cases:

| Topic/source | Publication versus event | Selection outcome |
|---|---|---|
| [NASA iROSA operations](https://www.nasa.gov/blogs/spacestation/2026/10/29/spacewalkers-install-roll-out-solar-arrays-for-power-generation/) | Published/event October 29, 2026; November 5 installation was a future plan in that article | Existing augmentation case covers the business decision |
| [JAXA OrigamiSat-2 cells](https://www.ihub-tansa.jaxa.jp/english/topics_Origamisat2_en.html) | Updated October 30, 2026; bus-power demonstration September 10; IV measurements since May 30 | Existing monitoring case; future degradation collection is not a measured lifetime result |
| [NASA lunar infrastructure solicitation](https://www.nasa.gov/news-release/nasa-calls-for-proposals-to-accelerate-lunar-surface-technologies/) | Announced September 8, updated September 28, 2026 | Existing lunar utility/distribution examples; solicitation is not operating hardware evidence |
| [NASA ESCAPADE](https://science.nasa.gov/science-research/heliophysics/nasas-escapade-completes-powered-earth-flybys-now-en-route-to-mars/) | Published November 9, 2026; flybys November 7 and 9 | Existing Mars pointing case |
| [ESA SOLARIS](https://www.esa.int/articles/about-us/directorates/technology-engineering-and-quality/solaris) | Page labels publication August 8, 2022; historical programme overview | Background, not newly invented news; SBSP delivery already implemented |

## Method and uncertainty

For paired before/after maximum powers in watts, define

```text
y_i = ln(P_after,i) - ln(P_before,i)
retention = exp(mean(y_i))
u_cal² = u_before² + u_after² - 2 rho u_before u_after
u_total² = sigma_repeat² / n + u_cal²
lower_retention = exp(mean(y_i) - Phi^-1(confidence) u_total)
accept electrical retention iff lower_retention >= minimum_retention
```

This is the geometric mean of paired ratios, estimating one common multiplicative retention; it is not the ratio of arithmetic mean powers. The covariance calculation follows the [NIST TN 1297 uncertainty propagation framework](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty). The normal distribution and known uncertainty assumptions are this study's model, not an ESA qualification standard. Calibration errors are jointly centered Gaussian in log power, constant throughout each campaign, independent of the independent Gaussian paired repeat errors. In log space the propagation is linear and exact for that model. Sigmas are dimensionless natural-log standard deviations, only approximately fractional errors when small.

`power_retention_acceptance` evaluates positive, finite, equally sized vectors. `plan_power_retention_test` evaluates assumed retention and repeat count without creating fake samples. Both return the uncertainty components, point-estimate baseline and guarded decision. The latter's planning bound is **not a pass probability**. Failure to clear the bound means insufficient evidence, not proof of damage or a mandatory replacement.

The uncertainty budget must be independently justified. Do not estimate a standard deviation from eight points and use it as known, infer calibration correlation from those repeats, duplicate rows to increase n, or combine multiple panels as repeat measurements of one panel. Equal calibration errors cancel only when a defensible shared calibration establishes that correlation. Uncorrected bias, drift, spectral mismatch, temperature differences, or correlated repeat noise invalidate the bound. The reported confidence concerns repeated experiments under the model, not a probability that this individual panel is conforming. Sequentially repeating tests until one passes also invalidates the fixed-test interpretation.

## Executed synthetic findings

Eight hand-constructed paired readings give **98.0001%** retention. Repeat log sigma is 0.01, before/after calibration log sigmas are each 0.02. All of these are **synthetic scenario inputs**, with no Da Vinci data imported. There are four acceptance scenarios and 32 planned sensitivities. Deterministic results are checked in as `reference_results.json`.

| Calibration correlation | 95% lower bound (8 pairs) | Electrical criterion |
|---:|---:|---|
| 0.0 | 93.5114% | Insufficient evidence |
| 0.5 | 94.7803% | Insufficient evidence |
| 0.9 | 96.4620% | Pass under assumptions |
| 1.0 | 97.4319% | Pass under assumptions |

The point-only baseline passes all four. Increasing independent paired repeats from 8 to 128 at correlation zero improves the bound by only **0.0317 percentage points**, to **93.5431%**, still insufficient. At the assumed observed retention, even infinitely many repeats cannot clear 95% with that independent campaign calibration budget. The useful next step is validating or reducing differential calibration uncertainty, not asserting that the actual repaired spacecraft panel passes or fails. Imaging, insulation, mechanical integrity, thermal cycling, radiation damage and flight qualification remain outside this electrical screen. A real operator must also check absolute available watts against bus demand: a high retained fraction of an undersized panel is insufficient.

## Reproduce

Python 3.13+, from repository root:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_panel_acceptance.py
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/panel_acceptance/run.py
uv run pytest tests/test_panel_acceptance.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest --cov=packages --cov=apps
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

The example and analysis run fully offline. NumPy/pandas are existing dependencies; plotting uses Matplotlib and the runner uses PyArrow for Parquet. No random input generation is used. Tests include a seeded 100,000-campaign coverage experiment, an independent SciPy normal-quantile oracle, calibration cancellation, repeat-count limits, scale invariance and invalid inputs.

The runner writes `outputs/panel_acceptance/{config.json,input_manifest.json,metrics.json,events.parquet,logs.jsonl,cases.csv,plans.csv,figures/acceptance.png}`. The manifest records source URLs/dates, licensing, units, evidence kinds and SHA-256 hashes of input, method, runner and example. `provenance.json` is the source record. Only attributed facts and links are used from ESA/NIST; no copyrighted article text, images or measurement dataset are redistributed. Original synthetic inputs and code use the repository's noncommercial license.

Sphinx automatically registers `examples/space_business/plot_panel_acceptance.py`; the research index links it explicitly. Package CI also runs it against the installed wheel. These changes remain unreleased until a separately authorized release.
