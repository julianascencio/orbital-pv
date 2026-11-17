# Combined-stressor evidence before a cell qualification commitment

This implements a bounded part of backlog **P8.3**, last reviewed October 3, 2026 (**45 days old** on November 17). It is not invented current news. DOE's [workshop summary](https://www.energy.gov/cmei/systems/2026-space-photovoltaics-workshop) recommends combined-stressor testing; the event was **June 2, 2026**, and the [dated announcement](https://www.energy.gov/cmei/systems/articles/ieso-holds-solar-space-workshop-advance-photovoltaics-orbital-and-lunar) was published **June 11**. The summary page reports an update on **September 28, 2026** (50 days before this run), but does not establish its initial publication date. Participant recommendations are not DOE commitments or qualification requirements.

The customer is a spacecraft-cell supplier's reliability lead deciding whether to budget a combined radiation/thermal campaign before using separate-test results in an EOL power commitment. Baseline: multiply separately measured retained fractions with a control correction. Alternative: compare that prediction with an explicitly ordered combined test. KPIs are combined retained power, baseline error and the interaction ratio with approximate empirical uncertainty. Business value is identifying evidence that invalidates the cheap separate-test assumption; no test cost, procurement saving or flight reliability is claimed.

## Selection and evidence

Reviewed main `40b64bc`, architecture, existing radiation/procurement/monitoring methods, connectors, analyses, example gallery and recent commits. No AGENTS.md was present. Open #45 (lunar charging) and #46 (CME monitoring) do not overlap and remain untouched. This is neither the existing single-panel acceptance bound nor deployment reliability trials. It adds a four-arm sample registry and interaction analysis, not a complete universal qualification registry.

The November 17 primary-source scan found no stronger new nonduplicative case: ISS array installation and NASA miniCAST overlap existing work; older ESA thin-film and deployment pages are not current results. DOE's space-PV overview covers cell durability and radiation needs without new measured campaign results. Lunar/Mars, orbital operations and SBSP analyses already exist; new funding or overview pages do not establish new performance evidence. The source-backed backlog therefore supplies this case.

All 24 power pairs are **synthetic**: six independent hypothetical samples per arm, with geometric retentions control 0.995, radiation 0.95, thermal 0.98, combined 0.84. Each sample starts at 1 W; deterministic log offsets supply within-arm variation. No DOE, ESA or flight measurements are imported. The provenance file defines hypothetical radiation/thermal levels and an ordered radiation-then-thermal combined protocol. Those labels do not generate the power values through a physical model. The method assumes randomized, comparable samples and identical measurement conditions, stress levels and hardware boundary. It cannot verify those assumptions from a CSV.

## Method

For each arm, `m = mean(log(P_after/P_before))`. The no-interaction prediction is `exp(m_radiation + m_thermal - m_control)`. The interaction log contrast is `m_combined - m_radiation - m_thermal + m_control`; its exponential is combined retention divided by the independent-stress prediction. Values below one indicate additional combined loss; above one indicate less loss than that baseline. This is the full contrast, not the factor-of-four-scaled interaction coefficient of a ±1-coded regression. [NIST factorial effects guidance](https://itl.nist.gov/div898/handbook/pri/section6/pri615.htm) provides methodological context.

The method resamples whole sample pairs independently within each arm, 4,000 times with seed 1711, then reports 2.5th/97.5th percentile bounds. These are **approximate bootstrap bounds**, not calibrated exact coverage, a DOE standard or flight qualification. Six samples per arm cannot represent rare failures. Bias, between-batch variation, calibration systematics, correlated exposure errors and unobserved failure modes are not included. Repeated measurements of one cell are not independent hardware samples. Unique IDs cannot prove independence. Mixed campaigns, missing arms and nonpositive powers are rejected. `extra_loss_supported` means the upper bootstrap log bound is below zero (with a 1e-12 numerical tolerance), not a causal or certification decision.

The multiplicative baseline is a hypothesis, not a law. Ordered and simultaneous stress protocols are not interchangeable. Measurement normalization, annealing/time history, dosimetry and real qualification requirements need separate treatment. No dose-to-power mapping or mission-lifetime extrapolation is performed.

## Executed synthetic findings

The separate-test baseline predicts **93.5678%** retention; the combined arm gives **84.0000%**, a **9.5678 percentage-point** gap. The interaction ratio is **0.897744**, with approximate 95% percentile bounds **[0.887036, 0.909188]**. Thus the constructed combined protocol retains about **10.23% less power relative to the separate-test prediction**. This supports including a combined arm in the hypothetical campaign, not a claim about any actual cell technology. Sensitivities at 84%, 90%, 93.5678% and 97% combined retention include harmful, null and beneficial interactions; null evidence must not be interpreted as proof of independence.

## Reproduction

Python 3.13+ from repository root:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/combined_stress/run.py
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_combined_stress.py
uv run pytest tests/test_stress.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest --cov=packages --cov=apps
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

Existing CSV ingestion and NumPy/pandas are reused; no new runtime dependencies or network requests. Matplotlib provides plots and PyArrow supports Parquet outputs. The runner writes config, hashed input manifest, metrics, events, logs, arm/sensitivity CSVs and `figures/interaction.png` to `outputs/combined_stress/`. Executed metrics are pinned in `reference_results.json`. The gallery and research index expose `plot_combined_stress.py`; installed-wheel CI executes it. Source facts/links are attributed, source text/images are not redistributed, and original synthetic data/code use the repository noncommercial license.
