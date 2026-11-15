# Solar tower charging: schedule before oversizing

NASA's [miniCAST component awards](https://www.nasa.gov/news-release/nasa-awards-moon-base-transportation-technology-science-projects/) were published and announced **November 7, 2026**, eight days before this November 15 study. Planned assembly and testing are future activities, not demonstrated performance. NASA identifies solar generation, storage and wireless delivery components; it publishes no operating profiles or charging ratings in this announcement.

The customer is a lunar surface power integrator deciding whether rover charging appointments can reduce required tower-bus peak capacity while meeting deadlines. Baseline: start every session at its release. Alternative: shift complete, noninterruptible sessions inside agreed windows. KPIs are peak requested bus W, requested receiver Wh, aggregate unserved bus Wh and final battery SOC. Value is a quantified capacity and test-planning tradeoff before procurement; no hardware price, monetary saving or flight reliability is claimed.

## Inputs and evidence

All numeric inputs are synthetic, not miniCAST specifications: three 400 W receiver requests, each lasting two hours inside a six-hour window; constant PV 500/700/900 W; housekeeping 100 W; delivery efficiency 0.6/0.8/1.0; 2,000 Wh battery initially at 80%, minimum 20%, maximum 95%, charge/discharge efficiency 95%, 500 W charge and 1,000 W discharge limits. The six-hour illuminated segment is not a measured lunar illumination profile and excludes the lunar night. Efficiency 1 is an ideal sensitivity endpoint. Session power does not include a realistic charging taper.

The existing free CSV loader ingests the pinned requests. Provenance records URL, publication/event/retrieval dates, units, source rights and evidence kinds. No measured dataset is imported. Source facts are attributed; no article text or imagery is redistributed. Synthetic inputs/code use the repository's noncommercial license.

Reviewed main `40b64bc`, architecture, connectors, EPS dispatch, workload scheduling, continuous service admission, analyses and gallery; no open PRs existed. Prior panel-acceptance PR #43 and solar-activity PR #44 were already merged. This adds **exact contiguous-session scheduling**, whereas existing compute scheduling is a preemptible energy-allocation heuristic and lunar utility admission assumes continuous loads. Existing battery dispatch and CSV ingestion are reused.

The primary-source news scan also found ESA's November 11 [open-space manufacturing demonstration](https://www.esa.int/articles/about-us/directorates/technology-engineering-and-quality/first-structure-3d-printed-in-the-extremes-of-open-space), which supplies no solar-generation operating data; October 26 [CRISTAL deployment testing](https://www.esa.int/media/about-us/directorates/earth-observation-programmes/copernicus/testing-cristal-s-solar-panel-deployment), already covered by deployment evidence; and NASA's lunar technology solicitation, already covered by utility/distribution studies. Existing Mars, perovskite/radiation monitoring, orbital operations and SBSP examples were inspected to avoid duplication. No new measured radiation or SBSP performance is inferred from these stories.

## Method

For each allowed integer start, bus demand is `base + sum(active receiver W / efficiency)`. Exhaustive enumeration selects the lexicographically smallest `(peak positive bus deficit, sum positive bus deficit, peak total bus demand)`; slot duration is uniform, so the second term is proportional to deficit energy. Ties select the earliest start tuple in input order. Every request must fit its window. Reject invalid inputs and searches exceeding 100,000 start combinations; this is a bounded small-fleet reference, not a scalable general optimizer.

Optimality is only over this discrete grid and objective. It does not optimize battery capacity, aging, SOC or cost. The existing energy-conserving `dispatch_power` subsequently tests the requested load with finite storage/power constraints. A lower deficit peak need not yield a globally optimal storage schedule for arbitrary variable profiles. No uncertainty distribution is asserted; the 18 cases vary efficiency and PV rating deterministically. Forecast error, link range/alignment, receiver battery limits, thermal constraints, travel time, charging taper and stochastic arrivals are omitted.

Dispatch shortfall is **aggregate bus energy** and is not attributed to a rover or housekeeping. A scheduled request is not proof of delivered energy when any shortfall occurs. Final SOC alone cannot establish service success. Nor does zero shortfall in one six-hour profile guarantee subsequent lunar-night service.

## Executed results

At 700 W PV and 80% delivery efficiency, scheduling starts at hours **0, 2 and 4**, reducing requested bus peak from **1,600 to 600 W (62.5%)**. The requested receiver energy remains **2,400 Wh**. Aggregate unserved bus energy falls from **660 to 0 Wh**, with both cases ending at 95% SOC: the baseline recharges after failing to serve its early peak. Even scheduling cannot remove energy scarcity: at 500 W PV and 60% efficiency it leaves **460 Wh** unserved and ends at 20% SOC. These are modeled findings, not actual miniCAST results.

`reference_results.json` contains all 18 executed cases. The plot contrasts load timing and efficiency sensitivity. A hand-checkable test proves the base-case peak is optimal: average bus demand is 600 W, a lower bound on any peak, and the schedule attains it.

## Reproduction and dependencies

Python 3.13+, from checkout root:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/lunar_charging/run.py
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_lunar_charging.py
uv run pytest tests/test_charging.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest --cov=packages --cov=apps
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

No new dependencies: NumPy/pandas for scheduling, Matplotlib for plots, PyArrow for runner Parquet. No credentials or network are needed for the case. Outputs under `outputs/lunar_charging/` include config, SHA-256 input manifest, metrics, event Parquet, logs, results/schedule CSV and `figures/charging.png`. Gallery discovery is automatic; the research index links the example and installed-wheel CI explicitly executes it.
