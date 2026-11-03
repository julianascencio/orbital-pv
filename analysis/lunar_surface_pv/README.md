# Lunar surface PV experiments

Run from an installed source checkout:

```bash
python -m pip install -e ".[examples,ground,orbit]"
python analysis/lunar_surface_pv/run.py --output outputs/lunar_surface_pv
```

The runner verifies the input manifest, recomputes all five modelling experiments
offline, and exports CSV/JSON: site/height/orientation comparisons, PV/battery
candidate sweeps, tower mass tradeoffs, a local yield map, thermal trajectories,
observed Diviner bins, a rover route and a numerical-resolution sensitivity check.
All six `examples/lunar/plot_*.py` scripts are also runnable individually and are
executed by the Sphinx gallery. The wheel supplies methods/connectors; runnable
analyses and their data live in the source checkout.

Compact [reference results](reference_results) are checked in for review. Their
summary records SHA256 fingerprints of the input manifest and analysis script.
Regenerating the analysis also writes full thermal trajectories and observation
tables, which are omitted from the compact reference directory.

## Rebuild inputs

```bash
python analysis/lunar_surface_pv/fetch_inputs.py --cache /path/to/lunar-cache
```

Four anonymous connectors download roughly 550 MB of original data the first
time. Later runs verify cached originals. Derived offline inputs are about 5 MB.
`examples/lunar/_data/provenance.json` records every original source URL,
retrieval time, SHA256, extracted file hash and transformation. No fabricated
fallback data is used. Updating inputs intentionally changes their manifest.

## Analysis design

- Three illustrative high points within PGDA Sites 01, 04 and 11, selected for
  reproducible comparison rather than certified landability.
- Panel heights 2, 5, 20 m; north-facing vertical arrays versus ideal Sun tracking.
- 5 m nearby terrain, 80 m intermediate terrain and broad 1280 m sampled terrain;
  spherical geometry, common observer height and sector maximum horizons.
- Full 2026 at 2 h intervals; July 1--31 at 30 min intervals for thermal modelling
  and numerical sensitivity. Year is not a full lunar precession cycle.
- 1 m² AM0 PV reference: 28% at 1361 W/m² and 25 C, relative -0.2%/K coefficient.
  Yield/storage use constant 25 C cells; thermal coupling is a separate experiment.
- 1 kW payload plus 103 W assumed heating. Batteries start at 50% SOC and must end
  at or above 50%, stay above 10% and below 95%, with 95% one-way efficiency,
  15 kW charging and 3 kW discharge limits. No temperature/ageing capacity model.
- Candidate array areas 6/10/16/25/40 m²; capacities 20/50/100/200/400/800 kWh.
  Panel/battery/tower masses are explicitly assumed, not OEM data.
- Diviner spatial percentiles are constant thermal-boundary scenarios. Source
  observations span 2009--2020, L_s 0--60°, subsolar longitude 0--15°. They do not
  describe temperatures at the simulated timestamps. Brightness temperature is
  converted to emitted flux with emissivity 1, avoiding double emissivity correction.
- Rover costs include ascent, rolling resistance, heating, housekeeping and
  battery losses, with four-neighbour movement/waiting and reserve constraints.
  The 12-hour window starts at the greatest spatial solar-power spread in July
  (while retaining a full window), deliberately illustrating mixed light.
  Mobility and hardware assumptions are illustrative.

NASA SVS images are qualitative references, never flux inputs. Terrain-error
maps are downloadable, but correlated uncertainties are not propagated. The
resolution comparison is numerical sensitivity, not a statistical interval.
Results are scenario calculations; there is no independent lunar PV telemetry
validation. See the [modelling guide](../../docs/sphinx/source/user_guide/modeling_topics/lunar_surface_pv.rst)
and [literature matrix](../../docs/literature/12_lunar_surface_pv.md) for boundaries.
