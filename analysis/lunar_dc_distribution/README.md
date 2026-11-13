# Lunar DC distribution: voltage, losses and conductor mass

## Decision and source-backed backlog

A lunar PV utility operator must choose a distribution voltage and conductor
area before committing to remote customer power. The KPI is terminal power
with at least 90% of source voltage at the receiver; the trade is resistive
loss and conductor mass. Cable mass affects delivered hardware requirements,
but no launch price, total-system mass saving or dollar ROI is assumed.

This is a backlog case, not a new flight result. NASA's [power technology
catalogue](https://www.nasa.gov/power/) describes a low-mass cable concept at
10 kV DC, 10 kW and up to 4 km. Its [June 2026 PDF version](https://www.nasa.gov/wp-content/uploads/2026/06/space-logistics-nasa-tech-catalog-final-20260610-v2-508complaint-signed.pdf)
contains 20260610 in the filename: **156 days before this November 13 review**.
That is a version-date age, not a verified publication or test date. No flight
performance or test-event date is inferred. Source retrieval and rights are
recorded in `provenance.json`. Source pages are linked, not redistributed.

The fresh-news review found orbital-compute solar claims already covered by
merged PR #40. Existing examples cover satellite arrays/cells, radiation,
Mars geometry, lunar utility storage and SBSP delivery. This distinct case
replaces a constant distribution-efficiency assumption with a resistive DC
load-flow calculation. No overlapping implementation or open PR was found.
The actual LunaGrid-Lite AC demonstration is not modeled by this DC method.

## Inputs, method and assumptions

The existing public CSV connector loads `lunar_dc_material.csv`. Every material,
area and voltage constraint is an illustrative assumption; NASA's scale provides
context, not calibrated hardware data. A 10 kW constant-power terminal load is
4,000 m from an ideal stiff source. Two equal conductors have assumed density
8,960 kg/m³ and operating resistivity 1.72e-8 ohm m. Areas are 1, 4 and 10 mm²;
voltages 400, 1,000, 3,000 and 10,000 V. Resistivity multipliers 1, 1.5 and 2
provide 36 cases; they are not statistical uncertainty or temperature predictions.

The reusable `orbitalpv.physics.dc_cable_delivery` computes loop resistance
`R = 2 rho L / A`, conductor-only mass `m = 2 L A density`, and the high-voltage
root of `Vr² - Vs Vr + R P = 0`. Current is `P/Vr`, cable loss `I²R`, and source
power `P + I²R`. A real equilibrium requires `P <= Vs²/(4R)`; the double root
is a maximum-transfer boundary, not an operating margin. Missing equilibria
return NaN for voltage/current/loss, never zero loss. A separate voltage check
requires `Vr >= 0.9 Vs` and strict separation from the maximum-transfer point.

The 400 V cases provide a low-voltage baseline. The model does not claim dynamic
stability of a converter-regulated load, even on the high-voltage root. Cable
ampacity, insulation mass/thickness, breakdown, arcing, connectors, voltage
regulation, converter efficiency, source PV capacity, storage, darkness, dust,
thermal radiation and mechanical deployment are excluded. The resistivity is
supplied at operating temperature, which is not solved. Passing the voltage
criterion is therefore **not** a qualified lunar-system design.

## Reproduction

Python 3.13+ with the repository uv workspace:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/lunar_dc_distribution/run.py
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_lunar_dc_distribution.py
uv run pytest tests/test_dc_distribution.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

No live data access or credentials are required after dependency installation.
The runner writes `outputs/lunar_dc_distribution` with CSV, Parquet events,
config, hashed input manifest, metrics, logs and a two-panel figure. The gallery
registers `plot_lunar_dc_distribution.py` automatically. Tests check an independent
analytic circuit, energy conservation, transfer boundary, monotonic trade-offs
and invalid inputs. These validate equations and implementation, not hardware.

## Executed modeled findings

At nominal assumed resistivity, the 400 V baseline has no equilibrium in any
of the three conductor sizes. At 1 kV and 10 mm², an equilibrium exists but the
receiver is only 835.26 V, failing the 90% criterion; cable loss is 1,972.30 W.
At 3 kV and 4 mm², the receiver reaches 2,880.58 V with 414.57 W loss and
286.72 kg of conductor. At 10 kV and 1 mm² it reaches 9,860.45 V with 141.52 W
loss and 71.68 kg of conductor. The latter is **75% less conductor mass** than
the 3 kV / 4 mm² case, not 75% less complete cable or system mass. Source PV/bus
power must cover load plus loss: 10,141.52 W in that 10 kV example, before
converter losses. Higher-voltage insulation and converter requirements could
reverse the total-system mass/cost advantage and require a separate design.

All results are modeled from the checked-in assumptions. No measured cable
efficiency, qualified mass, customer revenue or mission performance is claimed.
