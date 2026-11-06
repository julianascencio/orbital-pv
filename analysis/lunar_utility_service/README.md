# Lunar utility service admission

## Business decision and evidence

A lunar power-service operator must choose how many continuous customer loads to accept without consuming housekeeping reserves or relying on unreplenished battery energy. The news trigger is [Astrolab's 4 November 2026 LUMIS announcement](https://www.astrolab.space/2026/11/04/astrolab-unveils-lumis-power-and-communications-node-for-lunar-operations/), reviewed 6 November. Its planned node ratings and reserve-duration statement are manufacturer claims; no flight performance is verified here. The 2028 deployment is a target, not an operating asset.

Source metadata and assumptions are in `examples/space_business/_data/lunar_utility_provenance.json`. The existing tabular connector reads the original scenario CSV. No article text/images are redistributed. No new network scraper, dependency or incompatible storage format is introduced.

## Inputs and method

The synthetic illumination trace starts with 400 hours of darkness followed by 120 hours at constant PV output. Alternative cases change one factor: PV 2 to 20 kW; nominal battery 120 to 240 kWh; darkness 400 to 200 hours. These are assumed scenarios, not site-specific terrain or orbit results. In particular, the advertised reserve duration does not define a battery size or customer load.

Common assumptions: 50 W housekeeping, continuous 50 W delivered per customer, 90% delivery efficiency, 95% charge/discharge efficiency, initial SOC 90%, minimum 20%, maximum 95%, and 20 kW charge/discharge limits. Housekeeping must include mission-specific thermal and communications loads before operational use.

`orbitalpv.utility.screen_power_service` converts delivered customer power to utility-bus demand using `housekeeping + customer_count * customer_W / delivery_efficiency`. It reuses the existing energy-conserving `dispatch_power` model. Each of 0–12 customers is checked for total unmet bus energy <= 1e-6 Wh. Repeatable-profile feasibility additionally requires terminal SOC >= initial SOC (1e-10 tolerance). This guards against a misleading survival result financed by initial charge. The assumed future illumination profile must actually recur for this criterion to support repeated service.

The method reports aggregate shortfall, not customer-level service or prioritized housekeeping dispatch. A failed housekeeping-only case remains infeasible even at zero customers. Selecting the largest passing count is only an optimum within the supplied discrete grid.

## Results

With the reference assumptions, 2 continuous 50 W customers pass. Tenfold PV alone still admits 2. The larger-storage and shorter-darkness cases each admit 6. Thus delivered commitments rise from 100 to 300 W in the latter scenarios. These are modeled capacity limits, not actual LUMIS capability or service-level guarantees. No tariff, profit or return on investment is calculated without actual cost and revenue inputs.

The 52-row reference result includes finite-horizon feasibility, reserve restoration, repeatable feasibility, SOC and shortfall. Tests compare the dark-period shortfall with an independent energy equation and reject cases that survive but fail to recharge.

## Reproduce

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
PYTHONPATH=src uv run python analysis/lunar_utility_service/run.py --output outputs/lunar_utility_service
PYTHONPATH=src MPLBACKEND=Agg uv run python examples/space_business/plot_lunar_utility_service.py
uv run pytest tests/test_power_service.py
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
```

The deterministic, offline example appears under **Space PV business decisions**. Reference outputs include input SHA-256 and source provenance. No random seed or credentials are needed.

## Limits and next evidence

The screen excludes thermal transients, battery aging/self-discharge, failure probability, network redundancy, intermittent wireless links, rover charging schedules, terrain-derived illumination and economics. A zero-load grid result does not establish guaranteed availability. Require verified node telemetry, a measured/validated local illumination profile, thermal housekeeping, battery qualification and customer duty cycles before offering a service contract.

AI-assisted implementation for OrbitalPV / ASVA Consulting; human engineering review required for operational use.
