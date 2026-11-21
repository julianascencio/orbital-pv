# Sun-reacquisition battery reserve

## News and operator decision

NASA/JPL and Lockheed Martin's Odyssey operations teams face an attitude-control recovery decision. NASA's [report published November 19, 2026](https://science.nasa.gov/blogs/mars/2026/11/19/nasas-perseverance-odyssey-teams-investigate-technical-issues/) (page updated November 20, retrieved November 21) describes a reaction-wheel malfunction and paused science. The safe-mode event occurred **November 4–6**, not on publication day. Recovery testing was ongoing. The article supplies no battery SOC, power profile or engineering parameters for this calculation.

This reusable planning screen asks: **how long can an assumed loss of useful array pointing last before a specified load and terminal battery reserve become infeasible?** Compare continued normal demand with shedding discretionary loads during the delay. An operator could use calibrated telemetry and forecast bounds to set a recovery deadline and prioritize diagnostics over payload operations. Business value is protected service continuity and explicit lost-service tradeoffs; no revenue, fuel savings or actual mission life extension is claimed. It is not advice to operate Odyssey.

## Implementation and inputs

Reuse `orbitalpv.data.load_table` to import the checked-in four-phase CSV, and `BatterySpec` / `dispatch_power` for forward verification. No new connector or dependency is required. New `orbitalpv.physics.battery_reserve_envelope` returns the minimum stored Wh and SOC at every time boundary, or raises `InfeasibleReserveError` when no allowed initial SOC can satisfy the profile. It is an inverse energy calculation, distinct from the existing seasonal pointing screen and forward service dispatch.

All engineering inputs are **synthetic**, not fitted or measured. Source event metadata is imported factual context; results are modeled. At the spacecraft bus: 600 Wh nominal storage, initial/minimum/maximum SOC 0.70/0.10/0.95, charge/discharge efficiencies 0.95/0.90, and 400 W bus-side converter limits. Terminal SOC must be at least 0.50. During the variable delay, PV supplies 60 W and demand is either 300 W (normal baseline) or 120 W (load shedding). Restored pointing is followed by two assumed cycles, each 1.25 h at 650 W generation then 0.75 h eclipse at zero generation, with 300 W demand throughout. Starting restored operation in sunlight is an explicit assumption, not a reconstructed orbit. The complete power profile spans delay + 4 h.

## Method, units and limits

Let `R[i]` be minimum stored Wh at boundary i, `d` interval hours and `q = generation - demand` in bus-side W. Start from `R[N] = terminal_soc * capacity_wh`. For a deficit, `R[i] = R[i+1] - q*d/eta_discharge`; if `-q` exceeds the discharge limit, the profile is impossible. For surplus, `R[i] = max(E_min, R[i+1] - min(q, charge_limit)*d*eta_charge)`. If any required energy exceeds E_max, no initial SOC can make the complete profile feasible. Otherwise initial energy must exceed R[0]. Surplus curtailment is handled by the SOC bound; net horizon energy alone cannot resolve the timing constraints.

This recurrence is exact for the existing piecewise-constant EPS model, with fixed efficiencies and no self-discharge. It does not model attitude recovery, thruster fuel, bus voltage, load transients, battery aging/temperature, radiation damage or actual Mars orbit geometry. Infeasible outputs remain missing, with a reason, rather than being turned into zero required energy. Physical power/capacity infeasibility is distinguished from insufficient available initial SOC. Finite-profile success does not imply indefinite operation or flight qualification.

## Results and sensitivity

The 594 cases cover 33 delays from 0 to 8 h in 0.25 h steps, two load policies, capacities 450/600/750 Wh and PV multipliers 0.8/1.0/1.2 (applied to delay and restored generation). Every case checks inverse feasibility against forward unmet energy and terminal SOC. These ranges are stress assumptions, not confidence intervals.

At 600 Wh and nominal PV, the last passing sampled delay is **1.25 h normal versus 5.25 h with shedding**, a **4 h** increase. The next samples (1.50 and 5.50 h) fail. Thus the continuous thresholds lie in [1.25,1.50) and [5.25,5.50) h for this profile, not exactly at the grid results. Delaying restoration while shedding 180 W also defers 180 Wh of discretionary demand per hour; the scenario does not promise later catch-up. At 450 Wh, even full initial charge cannot meet the terminal target after the last 0.75 h eclipse: its maximum terminal SOC is 0.95 - 225/(450*0.9) = 0.3944. That constraint persists even with more sunlit PV. This is why energy timing and terminal reserve matter.

The figure displays the reserve requirement, a forward/backward SOC trace, and capacity/PV sensitivity. A missing point means no passing sample, not zero delay tolerance. `reference_results.json` records the executed baseline. The seed is null because the study is deterministic; randomized property tests separately use a fixed seed.

## Reproduce

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
MPLBACKEND=Agg PYTHONPATH=src uv run python examples/space_business/plot_sun_reacquisition.py
MPLBACKEND=Agg PYTHONPATH=src uv run python analysis/sun_reacquisition/run.py
uv run pytest tests/test_battery_reserve.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
```

Dependencies are already locked: NumPy, pandas, Matplotlib and PyArrow for analysis artifacts. The installed-wheel example uses the public API and is included in package CI. The runner writes config, source/units/license metadata with input and implementation SHA-256 checksums, metrics, scenario CSV, events Parquet, logs and a figure under `outputs/sun_reacquisition/`. No live data access is needed to reproduce. Source prose/images are not copied into the repository.

## News selection and overlap review (November 21)

Inspected default-branch architecture, methods, connectors, analyses, gallery and recent commits; open PRs #49 (qualification campaign) and #50 (ALISIO imaging) do not overlap this case. Other reviewed leads:

- [Boeing, November 19](https://www.boeing.com/features/2026/11/boeing-designed-solar-arrays-complete-space-station-power-upgrade): ISS upgrade is already covered by `array_upgrade_firm_power`; advertised generation is not telemetry.
- [Redwire, November 19](https://rdw.com/newsroom/redwire-awarded-15-million-contract-to-deliver-elsa-high-performance-low-mass-solar-array-wings-to-ascendarc-for-geo-communications-satellite/): GEO array contract awarded in Q3 FY2026; no usable mission power trace.
- [Redwire, November 10](https://rdw.com/newsroom/redwire-selected-for-40-million-contract-to-demonstrate-power-generation-for-nasa-moon-base-program-leveraging-its-innovative-roll-out-solar-array-technology/): lunar power demonstration plans, distinct from measured deployment; existing lunar utility/distribution/charging studies cover adjacent decisions.
- [JAXA, April 23](https://www.isas.jaxa.jp/home/research-portal/en/gateway/2026/0423/): radiation-tolerant cell research, paper published April 20; older evidence, not November news. Radiation and recovery analyses already exist.
- [ICEF November roadmap](https://icef.go.jp/wp-content/themes/icef_new/pdf/roadmap/2026/ICEF%20Space-Based%20Data%20Centers%20Roadmap%20Nov%202026.pdf): orbital power/data-center context; modeled concepts, not measured SBSP ground delivery. Existing compute/SBSP cases remain separate.

The selected November 19 Odyssey story supplies a new operational trigger, not an invented dataset or a backlog substitution.
