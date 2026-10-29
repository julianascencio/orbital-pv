# Case 0 — BIRDS telemetry baseline

This lab intentionally uses the **public `orbitalpv` API**, exactly as an external user would after installing the package from PyPI.

## Question
Can a lightweight, explainable baseline identify persistent PV under-performance from panel telemetry before orbit and radiation models are introduced?

## Install

```bash
python -m pip install orbital-pv
```

## Run

```bash
python labs/00_birds_baseline/run.py
```

The code starts with:

```python
import orbitalpv as opv

telemetry = opv.make_demo_telemetry(seed=42)
normalized = opv.add_robust_baseline(opv.add_power(telemetry))
health = opv.daily_health(normalized)
```

## Important limitation
Case 0 is deliberately **not** a physically normalized spacecraft PV model. Attitude, eclipse, solar distance, thermal response and radiation are confounders.
