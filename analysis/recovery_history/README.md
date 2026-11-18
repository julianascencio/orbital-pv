# Recovery credit and power-margin sizing

A space-cell supplier must decide whether to credit recovery when specifying beginning-of-life (BOL) cell power for a 1,000 W requirement. The baseline gives no recovery credit. The alternative uses a declared recovery history, with sensitivity to slower/faster recovery. KPI: minimum retained fraction and required pristine-reference BOL watts, not final recovered power. Business value is exposing the amount of capacity commitment that depends on unvalidated recovery kinetics; no monetary savings are estimated.

## Source and selection, retrieved November 18, 2026

[Electron irradiation tolerance of halide perovskite solar cells for space applications](https://doi.org/10.1016/j.solmat.2026.114494), Solar Energy Materials and Solar Cells, publication **October 15, 2026**, is **34 days old**. Its accessible primary abstract reports partial recovery of glass transmittance after natural aging or thermal annealing. Experiment dates and calibrated power-recovery rates were not established. Full text could not be retrieved; this is neither a reproduction nor a fitted model of that paper. No source measurements, tables or figures are redistributed.

This implements a bounded part of **P8.7**, last reviewed October 3 (**46 days old**). The November 18 news scan also found NASA's November 5 final ISS array installation and November 7 miniCAST awards, already covered by existing analyses/open PR #45. JAXA perovskite flight evidence overlaps existing monitoring; combined-stressor evidence overlaps #47, and storm operations overlap #46. No new nonduplicative mission data were inferred. The new November 11 perovskite review reinforces qualification gaps but supplies no calibrated kinetics here. Architecture, connectors, methods, analyses, gallery and main history were inspected; no AGENTS.md is present. Existing monotone radiation retention explicitly excludes annealing, so it remains unchanged.

## Inputs, model and limits

All input numbers are **synthetic assumptions**, all results are **modeled**. Four intervals are 2 h damaging exposure, 8 h recovery, then repeated once. Effective damage rate is 0.08 h^-1 during exposure; recovery rate is 0.15 h^-1 during recovery, multiplied by 0, 0.25, 0.5, 1 or 2. A fixed factor 0.98 represents pre-existing irreversible loss relative to pristine BOL; initial reversible deficit is zero. Neither rate is a particle flux or derived from the paper. All powers refer to the same cell electrical boundary at matched irradiance and temperature, not spacecraft-bus delivery.

The reduced kinetics are dD/dt = a(1-D) - rD, with D in [0,1]. For each constant-rate interval, D(t)=a/(a+r)+(D_start-a/(a+r))*exp(-(a+r)t). Zero total rate preserves state. Retention is 0.98*(1-D). Exact analytic interval means use expm1 for small arguments. Each interval is monotone, so its endpoints bound retention exactly. Required reference BOL power = 1000/minimum_retention. This is a capacity constraint, not an energy/storage simulation; no eclipse energy, heater demand, temperature dynamics, illumination response, cumulative irreversible damage or dose transport is modeled. Caller-supplied rates can represent declared environmental regimes only after independent calibration.

This is a phenomenological scenario model, not validated defect kinetics or material-specific space qualification. Rate multipliers are deterministic sensitivity bounds, not confidence intervals. No mission lifetime extrapolation is justified. Recovery could be absent, slower, or limited by irreversible damage; simultaneous exposure is mathematically supported but not experimentally validated. Calibration must use matched before/after power measurements with recorded temperature, illumination, dose, recovery time and device boundary.

## Executed results

No recovery: minimum retention **0.711626**, required **1,405.23 W**. Nominal recovery: minimum **0.797911**, final **0.925156**, required **1,253.27 W**. Thus nominal recovery credit reduces the assumed capacity requirement by **151.96 W (10.81%)**. Sizing from the final recovered value would miss the earlier minimum. At quarter-rate recovery, **1,344.76 W** is required. These are hypothetical sizing sensitivities, not demonstrated technology benefits. Original synthetic inputs/code follow the repository noncommercial license; source facts are attributed.

## Reproduction

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/recovery_history/run.py
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_recovery_history.py
uv run pytest tests/test_recovery.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest --cov=packages --cov=apps
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

No new dependencies: existing CSV ingestion, NumPy/pandas, Matplotlib and PyArrow. Runner writes config, input manifest with SHA-256 hashes/units/provenance, metrics, Parquet interval events, logs and a plot under `outputs/recovery_history/`. Reference results are pinned alongside this README. Gallery/API research indexes and installed-wheel CI include the example. Plot lines connect endpoints as visual guides, not a sampled continuous solution.
