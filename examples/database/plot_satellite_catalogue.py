"""
Satellite PV evidence coverage
==============================

Compare documented wattage evidence with gaps without adding incompatible ratings.
All records are loaded offline from the installed package. Historical designs,
ranges and conflicting source assertions count as documented, not validated telemetry.
"""

import matplotlib.pyplot as plt
import pandas as pd

from orbitalpv import catalogue

rows = catalogue.load_records("satellites")
frame = pd.DataFrame(rows)
print(
    frame.reindex(columns=["name", "pv_power_w", "power_basis", "power_conditions"]).to_string(
        index=False
    )
)

known = sum(row.get("pv_power_w") is not None for row in rows)
alternate = sum(
    row.get("pv_power_w") is None and bool(row.get("power_ratings_json")) for row in rows
)
missing = len(rows) - known - alternate
fig, ax = plt.subplots(figsize=(8, 4.5))
labels = ["Preferred qualified scalar", "Only alternate / range ratings", "PV wattage undocumented"]
counts = [known, alternate, missing]
bars = ax.barh(labels, counts, color=["#267c8c", "#e8ad55", "#b6c3d1"])
ax.bar_label(bars, padding=5)
ax.set(
    xlabel="Spacecraft records", title="Satellite PV evidence coverage", xlim=(0, max(counts) + 3)
)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
plt.show()
