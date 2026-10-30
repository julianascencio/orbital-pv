"""
Group mapped PV farms and test an area-capacity model
=====================================================

Convert raw OSM features into geometry, remove duplicate representations,
group nearby installations and attach historical settlement context. Keep
generator-group area separate from whole-plant land and landscape extent.

Calibrate the model form in `Dunnett et al. (2020)
<https://doi.org/10.1038/s41597-020-0469-8>`_ using the authors' original,
anonymised Wiki Solar join table. **Spain is completely withheld** from
calibration. The graph reports country-transfer error, not in-sample fit.
Source capacities are reported MW without an AC/DC declaration.

The historical profile uses the archived script's 400 m point / 800 m polygon
grouping settings. Its polygon-area proxy can include site land; it must not
be substituted for pixel-derived module area. The approximate prediction
interval omits mapping error and geographic domain shift. The substantial
held-out errors are part of the result.

GHSL uses epoch 2015, release R2023A, at native 1 km resolution. This later
edition differs from the paper's R2019A input. Here farm centroids are sampled,
rather than taking the original feature-centroid majority. These classifications
describe historical settlement context, not the land use at the image date.

Run with ``orbital-pv[ground,examples]`` and the companion ``_data`` folder.
All data are bundled, real snapshots with checksums. OSM © contributors,
ODbL; GHSL © European Union; calibration archive CC0. See ``_data/README.txt``.
"""

# sphinx_gallery_thumbnail_number = 2

import hashlib
import json
from pathlib import Path
from pprint import pprint

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import orbitalpv as opv

# %% Build three farm inventories and attach historical settlement classes

directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
data = directory / "_data"
inventories = {}
for name in ("cestas", "rengo", "tenerife"):
    mapped = opv.osm_pv_features(json.loads((data / f"{name}-osm.json").read_text()))
    farms = opv.cluster_pv_farms(mapped, profile="dunnett2020")
    settlement = opv.load_settlement_raster(data / f"{name}-ghsl.tif")
    inventories[name] = opv.classify_pv_farms(farms, settlement)

rows = [
    {"site": name, **feature["properties"]}
    for name, inventory in inventories.items()
    for feature in inventory["features"]
]
table = pd.DataFrame(rows)
pprint(
    table[
        ["site", "source_feature_count", "panel_area_m2", "osm_polygon_area_m2", "urban"]
    ].to_dict("records")
)

# %% Area definitions are different measurements
#
# Rinconada has no mapped generator-group area. A missing area is not zero.

fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
x = np.arange(len(table))
for shift, key, label, color in (
    (-0.2, "panel_area_m2", "Mapped generator-group area", "#149c95"),
    (0.2, "osm_polygon_area_m2", "Union of mapped polygon land", "#526f9a"),
):
    values = table[key].to_numpy(dtype=float) / 10000
    bars = ax.bar(x + shift, values, 0.4, label=label, color=color)
    ax.bar_label(
        bars,
        labels=[f"{v:.2f}" if np.isfinite(v) else "Unavailable" for v in values],
        padding=3,
        fontsize=9,
    )
    for position in np.flatnonzero(~np.isfinite(values)):
        ax.text(x[position] + shift, 0.65, "Unavailable", ha="center", va="bottom", fontsize=8)
ax.set(
    xticks=x,
    xticklabels=table.site,
    yscale="log",
    ylim=(0.5, 800),
    ylabel="Area [ha, log scale]",
    title="Area provenance prevents double counting",
)
ax.legend()
fig.supxlabel("© OpenStreetMap contributors (ODbL) · Snapshot 30 October 2026", fontsize=8)
plt.show()

# %% Calibrate with independent capacities, leaving Spain out

csv = data / "wiki_solar_join.csv"
metadata = json.loads(csv.with_suffix(".csv.meta.json").read_text())
assert hashlib.sha256(csv.read_bytes()).hexdigest() == metadata["sha256"]
reference = pd.read_csv(csv)
training = reference[reference.GID_0 != "ESP"]
held_out = reference[reference.GID_0 == "ESP"]
model = opv.fit_pv_capacity_model(
    training["panel.area"].to_numpy() * 1e6,
    training.power.to_numpy(),
    urban=training.urban.astype(bool).tolist(),
    capacity_basis="reported",
    area_basis="osm_polygon_proxy",
    source="Dunnett2020 Figshare v2 Wiki Solar; Spain withheld",
)
prediction = model.predict(
    held_out["panel.area"].to_numpy() * 1e6,
    urban=held_out.urban.astype(bool).tolist(),
    area_basis="osm_polygon_proxy",
)
metrics = opv.evaluate_pv_capacity(held_out.power.to_numpy(), prediction)
pprint(metrics, sort_dicts=False)

# %% Report held-out errors; do not substitute fit accuracy

valid = prediction.eligible
observed, estimated = held_out.power.to_numpy()[valid], prediction.mean_mw[valid]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
axes[0].scatter(observed, estimated, s=24, alpha=0.7, color="#526f9a")
maximum = max(observed.max(), estimated.max()) * 1.05
axes[0].plot([0, maximum], [0, maximum], "--", color="#555555", label="Exact agreement")
axes[0].set(
    xlabel="Reported capacity [MW]",
    ylabel="Estimated capacity [MW]",
    title=f"Spain: {metrics['n_evaluated']} evaluated, {metrics['n_withheld']} withheld",
)
axes[0].legend()
axes[1].hist(estimated - observed, bins=18, color="#149c95", edgecolor="white")
axes[1].axvline(0, color="#555555", linestyle="--")
axes[1].set(
    xlabel="Estimate - reported capacity [MW]",
    ylabel="Held-out records",
    title=f"MAE {metrics['mae_mw']:.2f} MW · RMSE {metrics['rmse_mw']:.2f} MW",
)
fig.suptitle("Country-held-out capacity validation · reported MW, AC/DC unspecified")
fig.supxlabel("Source: Dunnett (2020), Figshare v2 Wiki Solar calibration table · CC0", fontsize=8)
plt.show()

# %% Apply the calibrated area definition, with explicit eligibility checks

tenerife = opv.estimate_pv_farm_capacity(inventories["tenerife"], model)
pprint([feature["properties"] for feature in tenerife["features"]], sort_dicts=False)
