# CME forecast disagreement: budget PV monitoring windows

The [NASA CCMC Earth CME Scoreboard](https://ccmc.gsfc.nasa.gov/CMESB-Earth/) lists an eruption first seen **November 14, 2026 at 22:15 UTC**, with two individual arrival forecasts submitted **November 15 at 14:34 and 14:53 UTC**. Retrieved November 16; source page last updated November 16. NASA M2M gives November 18 07:00 UTC ±7 h; UMA SARM gives November 17 10:37 UTC without published bounds. These are **experimental research predictions**, not observed arrivals or official operational forecasts. Their central times differ by **20 h 23 min**.

The customer is a satellite PV performance research team deciding how much telemetry capacity to reserve for higher-cadence panel voltage/current/temperature measurements around a possible space-weather event. Baseline: one window centered on the computed mean arrival, ±7 h. Alternative: preserve individual forecast windows and merge overlaps, explicitly supplying a planning buffer where a bound is missing. KPIs are monitoring hours, sample count and telemetry bytes. Business value is sizing a bounded acquisition reservation without treating disagreement or missing uncertainty as a precise arrival. This is not an automated spacecraft command, protection recommendation, impact forecast or monetary benefit estimate.

## Evidence and reuse

The pinned CSV imports the two forecast times, submission timestamps and published M2M bounds. No measured PV data are available here. Auto-generated ensemble rows are excluded to avoid counting them as independent models. SARM padding, midpoint width, cadence and sample size are author assumptions. The existing CSV connector suffices; no new network adapter or dependencies are needed. Existing NOAA/DONKI/solar activity connectors remain unchanged. Review covered architecture, analytics, environmental connectors, gallery, recent main commits and open PR #45. That PR concerns lunar charging and remains untouched. Existing radiation, lunar/Mars, cell procurement, orbital operations and SBSP studies do not implement timestamp-aware forecast-window budgeting.

The November 16 news scan also returned NASA's November 7 miniCAST announcement (already addressed by open #45), older cell-manufacturing announcements, and the November 2 NOAA weekly report covering October 26–November 1. Those dates were not relabeled as current events. The fresh CME submissions provide the selected new evidence. No new radiation degradation, lunar performance or SBSP efficiency result is inferred.

## Method and boundaries

`forecast_monitoring_windows` accepts one version per method for one event. It requires timezone-aware timestamps, excludes submissions after a declared as-of cutoff, rejects duplicate methods, and refuses missing bounds unless a positive explicit fallback is supplied. For each arrival t, form `[t-before, t+after)`. Sort and merge overlapping/touching intervals; retain gaps and clip past portions at the cutoff. These are input/planning windows, **not calibrated confidence intervals**. No assumption of independence, likelihood or occurrence probability is made.

`monitoring_sample_budget` computes `sum(ceil(window_seconds/cadence_seconds))` samples, with each window sampled at its start and excluding its end. Bytes equal samples × assumed payload bytes; packet overhead, compression and retransmission are excluded. Sampling restarts at each disjoint window. No spacecraft orbit, eclipse, data-downlink opportunity, sensor dynamics, dose, PV damage or causal attribution is modeled. A CME may miss Earth entirely. These windows need not contain its arrival, and even containing an Earth arrival does not guarantee detecting a satellite PV effect. Official operational information is available from [NOAA SWPC](https://www.swpc.noaa.gov/).

## Executed results

At a 60 s cadence and 256 bytes/sample, the midpoint baseline is **14 h, 840 samples, 215,040 bytes**. A ±12 h missing-bound assumption produces **38 h across two windows, 2,280 samples, 583,680 bytes**. It costs **368,640 additional bytes** under these assumptions. The gap between these windows is **1 h 23 min**; merging into a single envelope would unnecessarily include that gap. Neither policy is a probability-based coverage guarantee.

Missing-bound sensitivities ±6/12/24 h produce **26/38/51.3833 h**, respectively. At 600 s cadence the ±24 h case needs 309 samples rather than 308.3: partial intervals require a real sample. The source mean/median are not used as extra evidence; the baseline mean is computed from the two individual centers (20:48:30 UTC November 17). This differs from the source's minute-rounded display.

## Reproduce

Python 3.13+, repository root:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/cme_monitoring/run.py
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_cme_monitoring.py
uv run pytest tests/test_monitoring_windows.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest --cov=packages --cov=apps
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

NumPy/pandas are existing runtime dependencies, Matplotlib plots and PyArrow supports runner Parquet. The case runs offline. Outputs in `outputs/cme_monitoring/` include config, hashed input manifest, metrics, event Parquet, interval/results CSVs, logs and figure. `reference_results.json` retains all eight scenario results. Provenance records source dates, evidence labels, units and rights. Only factual forecast metadata is transcribed and attributed; source text/images/model software are not redistributed. Generated analysis/code uses the repository noncommercial license. The gallery discovers `plot_cme_monitoring.py`, with an explicit research-index link and installed-wheel smoke test.
