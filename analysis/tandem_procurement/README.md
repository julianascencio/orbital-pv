# News to business case: tandem-array procurement

**Decision:** how much can a constellation operator pay for a higher-power array at equal five-year end-of-life (EOL) sunlit bus power?

## Evidence and inputs

[Swift Solar, 3 November 2026](https://www.swiftsolar.com/news/space-solar-is-going-gigascale), reviewed 4 November, motivates a 20% BOL uplift scenario. The supplier's cell-level claim does not validate deployed-array mass, AM0 power or five-year retention. This analysis uses no measured flight data and makes no technology qualification claim.

`examples/space_business/_data/array_offers.csv` contains **modeled inputs**, loaded through the validated `orbitalpv.procurement.load_array_offers` connector (CSV, Excel and Parquet via the existing tabular connector). `provenance.json` separates the source claim from every assumed input. No copyrighted article or images are redistributed.

| Input | HJT scenario | Tandem scenario | Evidence |
|---|---:|---:|---|
| Array BOL power at common design point | 300 W/m² | 360 W/m² | Assumed; relative uplift tests supplier claim |
| Five-year EOL retention | 85% | 85% | Assumed, not radiation qualification |
| Deployed array areal mass | 2 kg/m² | 2 kg/m² | Assumed, includes allocated structure |
| Array procurement | 1,000 USD/m² | 1,500 USD/m² | Assumed, no quotes |

Common assumptions: 10 kW EOL sunlit bus demand, 20% power margin, 90% bus efficiency and 5,000 USD/kg **marginal** launch cost. BOL power already includes packing and the common thermal/illumination design point; the model does not convert terrestrial efficiency to space efficiency.

## Method

For each option let `q = BOL_W_m2 × EOL_retention`. Area is `required_bus_W × (1 + margin) / (q × bus_efficiency)`. Mass is area times areal mass. Total cost is area times `(procurement_USD_m2 + mass_kg_m2 × launch_USD_kg)`.

At equal delivered EOL power and common bus efficiency/margin, the maximum candidate procurement price is:

`candidate_price_ceiling = (q_candidate / q_baseline) × (baseline_price + baseline_mass × launch_price) − candidate_mass × launch_price`.

Negative ceilings mean that even free candidate hardware loses on modeled launch cost. The method is reusable for other cell/array technologies; it does not infer physical retention from mission duration.

## Reproduce

From the repository root:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
uv run python analysis/tandem_procurement/run.py --output outputs/tandem_procurement
MPLBACKEND=Agg uv run python examples/space_business/plot_tandem_procurement.py
uv run pytest tests/test_procurement.py
uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
```

The gallery discovers `examples/space_business/README.txt` and `plot_tandem_procurement.py` automatically. The runner writes sizing, a 184-case retention/launch-price sweep and a source-linked summary with input SHA-256. No network, credentials or randomness is required to reproduce this case. Executed reference outputs are in `reference_results/`.

## Findings and decision

At equal 85% retention, area falls from 52.29 to 43.57 m²; modeled mass falls from 104.58 to 87.15 kg. At the assumed launch price, total procurement-plus-launch cost falls from $575,163 to $501,089: $74,074 lower. The conditional candidate price ceiling is $3,200/m², or 220% above the baseline procurement price.

With **zero marginal launch cost**, the ceiling falls to $1,200/m²: the assumed $1,500/m² candidate is then more expensive. At $5,000/kg launch cost and the assumed candidate price, retention must reach about **74.05%** to break even against an 85%-retaining baseline. These are model thresholds, not a recommendation to buy unqualified hardware.

Next evidence to request: array-level AM0/thermal characterization, degradation at the mission's actual radiation/thermal exposures, deployed mass, integration/qualification cost and actual procurement/launch quotes. A cell power increase alone is insufficient to establish lifecycle value.

## Limits

This screens continuous array area at one sunlit operating point. It excludes eclipse storage, energy yield, pointing/shading variability, deployment probability, panel discretization, thermal redesign, fixed qualification and integration cost, schedule risk, insurance, revenues, discounting and staged launch prices. It does not predict five-year survival or continuous payload power. Equal array mass is especially uncertain when translating cell claims to a deployable system. Replace modeled offers with traceable engineering inputs before any procurement decision.

AI-assisted implementation and analysis for OrbitalPV / ASVA Consulting; human engineering review required before operational use.
