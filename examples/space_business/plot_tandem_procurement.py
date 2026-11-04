"""
When is a tandem array worth its price premium?
==============================================

A constellation procurement team needs 10 kW at its five-year end-of-life
sunlit design point. Swift Solar's November 3, 2026 announcement motivates
examining a 20% BOL power gain. This is a conditional array-level scenario,
not verified product performance. Source:
https://www.swiftsolar.com/news/space-solar-is-going-gigascale

The shared tabular input connector loads explicitly modeled offers. All prices,
masses, absolute power density and retention are illustrative assumptions.
A 20% design margin and 90% bus efficiency are common to both offers.
No AM1.5 efficiency is converted into AM0 array power. No eclipse or battery
model is implied: 12 kW here is sunlit design power, not continuous payload power.

We solve for the maximum candidate procurement price at equal EOL bus power,
then vary unknown lifetime retention and marginal launch cost. A negative
ceiling means even a free candidate array cannot compensate for its launch mass.
"""

from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from space_pv_analytics.procurement import ArrayOffer, break_even_cost_m2, size_array
from space_pv_connectors.procurement import load_array_offers

inputs = load_array_offers(Path(__file__).parent / "_data/array_offers.csv")
offers = [
    ArrayOffer(**row)
    for row in inputs[["name", "bol_w_m2", "eol_retention", "kg_m2", "cost_m2"]].to_dict("records")
]
baseline, candidate = offers
results = [size_array(offer, 10_000, launch_cost_kg=5000) for offer in offers]
for offer, result in zip(offers, results, strict=True):
    print(
        f"{offer.name}: {result.area_m2:.2f} m², {result.mass_kg:.2f} kg, ${result.total_cost:,.0f}"
    )
ceiling = break_even_cost_m2(baseline, candidate, launch_cost_kg=5000)
print(f"Conditional tandem price ceiling: ${ceiling:,.0f}/m²")

# %% Equal EOL power: procurement and marginal launch cost
fig, ax = plt.subplots(figsize=(8, 4.5))
labels = [offer.name for offer in offers]
procurement = np.array([result.procurement_cost for result in results]) / 1000
launch = np.array([result.launch_cost for result in results]) / 1000
ax.bar(labels, procurement, label="Assumed procurement", color="#167d9a")
ax.bar(labels, launch, bottom=procurement, label="Assumed marginal launch", color="#e7ae4c")
ax.set(
    ylabel="Modeled cost [thousand USD]",
    title="Equal 12 kW EOL sunlit bus power; illustrative costs",
)
ax.legend()
fig.tight_layout()
plt.show()

# %% Qualification target: retention versus affordable procurement premium
retentions = np.linspace(0.55, 1.0, 91)
fig, ax = plt.subplots(figsize=(8, 5))
for launch_price in (0, 1000, 5000, 10_000):
    premiums = [
        100
        * (
            break_even_cost_m2(
                baseline,
                replace(candidate, eol_retention=float(retention)),
                launch_cost_kg=launch_price,
            )
            / baseline.cost_m2
            - 1
        )
        for retention in retentions
    ]
    ax.plot(retentions * 100, premiums, label=f"Launch ${launch_price:,}/kg")
ax.axhline(50, color="black", linestyle="--", label="Assumed candidate price: +50%/m²")
ax.axvline(85, color="gray", linestyle=":", label="Assumed baseline retention: 85%")
ax.set(
    xlabel="Candidate five-year EOL retention [%; unvalidated]",
    ylabel="Break-even procurement premium over HJT [%/m²]",
    title="Higher BOL power alone does not establish lifetime value",
)
ax.legend(fontsize=8)
ax.grid(alpha=0.2)
fig.tight_layout()
plt.show()

# %% Decision and limits
# At equal 85% retention and $5,000/kg marginal launch cost, the ceiling is
# $3,200/m² (+220%). With zero marginal launch cost it drops to $1,200/m²
# (+20%), below the assumed $1,500/m² candidate price. The purchase decision
# therefore depends on realized launch savings and qualification, not BOL gain alone.
# Costs omit qualification, deployment risk, discrete array sizes, storage,
# integration overhead, launch pricing steps, revenue and discounting.
# Require common-condition AM0/thermal tests, flight-relevant degradation evidence,
# deployed-array mass and actual quotes before procurement.
