# SBSP delivery adequacy for a datacenter offtaker

## Evidence and decision

This implements the unimplemented P7.3 delivered-power backlog. On **September
30, 2026**, Virtus Solis announced a proposed supply agreement with Brae Systems:
100 MW continuous power and 876,000 MWh annually. Publication and announcement
dates coincide; neither is an operational delivery date. The story is **39 days
old** at the November 8 review, not newly breaking news.

Primary sources, retrieved November 8, 2026:

- https://www.virtussolis.space/blog/virtus-solis-signs-landmark-20-year-ppa-with-brae-systems
- https://www.prnewswire.com/news-releases/virtus-solis-signs-landmark-20-year-space-solar-ppa-with-brae-systems-to-deliver-250-mw-of-orbital-baseload-clean-power-302894283.html
- https://www.ard.jaxa.jp/eng/research/ssps/ssps.html (conversion/transmission research context, no dated operational claim)

A datacenter offtaker must decide whether an offered delivery profile supports
its continuous load and what backup duty remains. Baseline: ideal uninterrupted
100 MW at the ground delivery boundary. Constraints: a constructed 8760-hour
year, 100 MW constant load, no storage or grid contribution, no overbooking of
transmitters, and nonnegative interval-average power. KPIs: delivered and served
energy, positive shortfall, time-weighted availability, peak backup power, longest
shortfall and largest uninterrupted energy deficit. Business value: avoid
accepting annual MWh as evidence of continuous service and identify the backup
duty to take into further engineering. No contract prices or savings are assumed.
These are engineering screens, not conclusions about unpublished PPA clauses.

## Review scope and reuse

The review found no open PRs; #36 monitoring was merged. Recent JAXA perovskite
bus-power news (October 30 update; September 10 event) is covered by #36:
https://www.ihub-tansa.jaxa.jp/english/topics_Origamisat2_en.html . NASA's October
15 array overview is relevant to orbital operations but overlaps the existing
array-upgrade study:
https://www.nasa.gov/missions/station/iss-research/power-up-roll-out-solar-arrays-boost-space-station-power-supply/ .
DOE's August 31 space-PV funding article covers radiation/durability and cell
manufacturing, but its October 8 deadline has passed:
https://www.energy.gov/cmei/articles/does-office-critical-minerals-and-energy-innovation-announces-first-major-investment .
Lunar/Mars searches did not establish a suitable distinct recent numerical-data
story; existing lunar utility and Mars models were retained. No invented news.

Existing `load_table` reads the original scenario CSV. No new remote connector
is needed: only advertised target numbers are imported manually, with URLs,
retrieval date and rights in `sbsp_provenance.json`. There is **no measured flight
or receiver data**. Existing loss accounting handles attributed telemetry gaps;
this new analytics module handles explicit interval-average powers, delivery
adequacy and contiguous deficit events, without interpolating between samples.

## Method and assumptions

`orbitalpv.delivery.delivery_chain` applies an ordered product of conditioning,
DC/RF, beam capture, RF/DC and grid efficiencies to PV DC watts. It returns each
cumulative stage for audit. Efficiencies are analyst assumptions, not measured
supplier performance. This is a conservation/accounting model, not an RF beam,
orbital geometry or thermal simulation.

`assess_delivery` takes N+1 elapsed-hour boundaries and N interval-average powers
(or scalars). For each interval, served = min(delivered, required), deficit =
max(required-delivered, 0), surplus = max(delivered-required, 0). Multiply each
by its actual duration to get Wh. Thus served+deficit=required and
served+surplus=delivered. No annualization is implicit. Missing/negative/nonfinite
powers and invalid boundaries fail explicitly. Callers must account for every
interval; edges alone cannot reveal a hidden missing observation.

Availability is the duration with deficit <= the specified watt tolerance,
divided by total duration. Tolerance affects event classification only, never
shortfall energy. The example uses 1e-6 W for floating-point noise. Consecutive
above-tolerance intervals form an event. Events crossing the end/start of the
finite horizon are not wrapped. Interval averages cannot resolve sub-hour
interruptions. Backup peak W and largest event Wh are ideal point-of-delivery
requirements, not battery capacity ratings: SOC, recharge, efficiencies, reserves,
power ramping and redundancy require separate dispatch/sizing studies.

The 28 cases compare two baseline/illustrative profiles and twelve PV/capture
sensitivities, each with clustered versus distributed outages. Sensitivities use
PV DC 160/200/250/300 MW; conditioning .95, DC/RF .7, capture .6/.8/1,
RF/DC .85, grid .98. Every interrupted case has 88 zero-generation hours,
either hours 0–87 or one hour every 99 hours. These deliberately constructed
sequences are not orbital eclipse or failure forecasts. No probabilities or
confidence intervals can be inferred from this grid. Radiation, aging, weather,
receiver limits and handovers could change both profiles and efficiencies.

## Executed results

The illustrative 210 MW PV / 50% chain profile gives 105 MW when available:

| KPI | Clustered | Distributed |
|---|---:|---:|
| Delivered energy | 910,560 MWh | 910,560 MWh |
| Required energy | 876,000 MWh | 876,000 MWh |
| Served load | 867,200 MWh | 867,200 MWh |
| Shortfall | 8,800 MWh | 8,800 MWh |
| Availability | 98.9954% | 98.9954% |
| Peak backup duty | 100 MW | 100 MW |
| Longest shortfall | 88 h | 1 h |
| Largest event deficit | 8.8 GWh | 0.1 GWh |

Both exceed the advertised annual target by 34,560 MWh but fail continuous
service without backup. Annual surplus must not be subtracted from outage
energy. The 88× event-energy difference shows why chronology matters even
when energy and availability match. Neither result predicts supplier performance.

## Reproduction

Python 3.13+, existing NumPy/pandas/Matplotlib; PyArrow for the runner's Parquet:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
PYTHONPATH=src MPLBACKEND=Agg uv run python analysis/sbsp_delivery/run.py
PYTHONPATH=src MPLBACKEND=Agg uv run python examples/space_business/plot_sbsp_delivery.py
uv run pytest tests/test_delivery.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
MPLBACKEND=Agg uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

The runner writes config, checksum manifest, metrics, logs, scenarios.csv,
events.parquet (scenario-level event summaries), and figures/delivery.png under
outputs/sbsp_delivery. No random draws; seed is null. `reference_results.json`
contains the executed comparison. The gallery auto-discovers the `plot_` example
and the research index links it. Tests verify duration weighting, energy balances,
event chronology, tolerance, boundary cases and rejected invalid inputs.
Source texts/images are not redistributed. Original code/scenarios use the
repository license; source rights remain with their owners.
