# Planning laboratory effort without inventing qualification evidence

Customer: a space-PV panel supplier's test manager. Decision: choose proposed tests within a lab-effort budget, with explicit uncovered requirements. Baseline: one standalone test for each requirement. KPI: covered priority weight, planned hours and the uncovered requirement list. Business value: expose the resource and protocol assumptions behind a proposed campaign before reserving lab capacity. No monetary savings, flight reliability or certification are inferred.

## Source and age

DOE's [2026 Space Photovoltaics Workshop](https://www.energy.gov/cmei/systems/2026-space-photovoltaics-workshop) recommends mission-specific qualification protocols and combined-stressor testing. The event occurred **June 2, 2026**; the page reports an update **September 28**; initial publication date is not established. These are participant recommendations, not DOE commitments or standards. Retrieved **November 19, 2026**.

This implements a bounded planning component of backlog **P8.4**, last reviewed October 3 (**47 days old**), not invented fresh news or a complete qualification evidence database. Recent scans covered NASA's [November 5 ISS array installation](https://www.nasa.gov/blogs/spacestation/2026/11/05/spacewalkers-install-final-roll-out-solar-array/), [November 7 lunar awards](https://www.nasa.gov/news-release/nasa-awards-moon-base-transportation-technology-science-projects/), JAXA's [October 30 update](https://www.ihub-tansa.jaxa.jp/english/topics_Origamisat2_en.html) on September 10 bus-power delivery, and ESA's [October 26 deployment-testing report](https://www.esa.int/media/about-us/directorates/earth-observation-programmes/copernicus/testing-cristal-s-solar-panel-deployment). Those topics overlap implemented power, monitoring, charging and deployment analyses. Radiation/recovery and combined-stress work is now merged. Lunar/Mars and space-based solar power scans supplied no stronger new numerical evidence. Main, architecture, connectors, methods, analyses, gallery and recent commits were reviewed; no open PRs or AGENTS.md were found.

## Inputs and interpretation

Every requirement, priority, proposed coverage edge and lab-hour estimate is **synthetic**. No observed test result is loaded. Existing CSV ingestion is reused. Four hypothetical panel requirements represent radiation, thermal, vacuum and deployment coverage, with weights 4, 3, 2 and 1. Standalone effort is 3, 3, 2 and 2 hours. Two hypothetical integrated campaigns require 5 and 3 hours and are assumed to cover pairs of requirements. Hours represent budgeted lab effort, **not physical exposure duration**, elapsed schedule, staffing or a complete space qualification campaign.

Coverage edges are reviewer-supplied planning assumptions. Shared mission and panel boundary are necessary filters, not sufficient evidence of protocol equivalence. Actual severity, sample counts, specimen independence, test ordering, acceptance criteria, standards applicability, flight correlation and pass/fail evidence require mission-assurance review. Bundled coverage is valid only if each requirement's protocol is actually satisfied; physical interference or shared specimens may invalidate it. No test selection is a completed or passed test. The output always states `qualification_demonstrated=False`.

## Method and sensitivity

The planner exhaustively enumerates all test subsets up to 18 candidates (262,144 subsets), rejects those over budget, maximizes the sum of distinct covered requirement weights, then minimizes hours and sorted test IDs for deterministic ties. A requirement covered twice is counted once. This is a weighted budgeted coverage model; weights are priorities, not probabilities. The final matrix lists selected supporting tests and uncovered requirements. Missing coverage is retained, not treated as a pass. No partial tests, dependencies, resource scheduling or uncertainty distribution is modeled.

The full-coverage baseline totals **10 h**. With the assumed integrated-test mappings, the exact full-coverage plan costs **8 h**, a **2 h (20%)** reduction in hypothetical effort. A budget sweep from 0 through 10 h exposes incomplete plans. Withdrawing the combined radiation/thermal test's thermal coverage edge tests how the plan changes when protocol equivalence is not accepted. At the same 8 h budget, withdrawing that edge selects three standalone tests, covers weight 9 of 10 and leaves deployment uncovered. These are deterministic scenarios, not confidence bounds or measured savings. They demonstrate why a coverage claim should be reviewed before lab reservations.

## Reproduction

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/test_campaign/run.py
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_test_campaign.py
uv run pytest tests/test_campaign.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest --cov=packages --cov=apps
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

Existing pandas/Matplotlib/PyArrow dependencies suffice. Outputs under `outputs/test_campaign/` contain config, SHA-256 input manifest with provenance/units, metrics, planned coverage CSV, Parquet budget scenarios, logs and a plot. Reference metrics are pinned here. The gallery/research/API indexes and installed-wheel CI include the example. Source facts are attributed; no source text/images are redistributed. Original code and synthetic data use the repository noncommercial license.
