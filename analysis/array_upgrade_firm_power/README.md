# Solar augmentation and continuous bus power

NASA's [2 November 2026 update](https://www.nasa.gov/blogs/spacestation/2026/11/02/week-starts-with-spacewalk-preps-and-life-science/) describes the final ISS array installation planned for 5 November. Completion was not verified at review on 5 November. The approximate 160-to-215 kW headline motivates scenario scales only: the source does not establish a sunlit bus-power time series. This is not an ISS operational forecast.

## Decision and evidence

A station operator considering additional continuous payloads must decide whether solar augmentation alone suffices or whether storage also needs enlargement. The KPI is sustainable **total** constant bus load, before subtracting essential loads and reserves. No monetary return is calculated without prices and payload value.

Reuse `orbitalpv.data.load_table` for the source-linked scenario CSV and existing `BatterySpec`/`dispatch_power` for independent interval simulation. New `orbitalpv.physics.periodic_load_limit` provides the reusable analytical bound. No redundant web scraper or new dependency is needed. All inputs are modeled, not telemetry. The provenance JSON distinguishes source facts, dates and assumptions; article text and images are not redistributed.

## Method and assumptions

Assume constant sunlit PV power P, zero eclipse power, sunlight duration s, eclipse duration e, charge/discharge efficiencies ec/ed, nominal capacity B, usable SOC window d, and bus-side converter limits C/D. For e > 0 the sustainable constant load is:

`min(P*s/(s+e/(ec*ed)), B*d*ed/e, C*ec*ed*s/e, D)`.

This enforces orbit-energy balance, eclipse storage capacity, recharge power and discharge power simultaneously. Initial SOC is irrelevant to periodic feasibility; startup is a separate dispatch question. With no eclipse the limit is P. Units: W, Wh and hours.

Scenarios assume 60 minutes sunlight, 35 minutes eclipse, 95% efficiency each way, SOC 20–90%, 200 kW converter limits, and nominal storage of 80 or 120 kWh. The 366-case sensitivity varies eclipse duration (20/35/45 minutes), storage (40–160 kWh) and solar input (160/215 kW). Two-cycle dispatch verifies each reference result without unmet load or declining end-cycle SOC.

## Reproduce

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
PYTHONPATH=src uv run python analysis/array_upgrade_firm_power/run.py --output outputs/array_upgrade_firm_power
PYTHONPATH=src MPLBACKEND=Agg uv run python examples/space_business/plot_array_upgrade_firm_power.py
uv run pytest tests/test_periodic_load_limit.py
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
```

The example is automatically registered under **Space PV business decisions**. Committed reference results include input SHA-256 and provenance. Offline inputs are deterministic and require no credentials.

## Results

With 80 kWh storage, both PV scenarios sustain 91.20 kW: extra PV alone adds zero continuous capacity. With 120 kWh storage and 215 kW PV, the bound rises to 130.59 kW, a 39.39 kW increase (43.19%). These are conditional model outputs, not measured station performance.

## Limits

Do not use these values as real ISS payload allocations. Real design needs measured solar generation, channel redundancy, essential-load profiles, orbital variability, reserves, thermal limits, radiation degradation, battery aging, mass, deployment risk and quotations. The chosen 160/215 kW scales do not independently verify NASA's rounded percentage statement. Periodic feasibility does not guarantee arbitrary initial SOC or fault survival. No optimization of varying loads is attempted.

AI-assisted implementation for OrbitalPV / ASVA Consulting; engineering review required for operational use.
