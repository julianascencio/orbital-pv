"""
Geographic holdout on real Sentinel-2 imagery
=============================================

Train a supervised logistic baseline on Cestas and evaluate only in Tenerife.
Compare the exact published ANDPI histogram rule as an explicitly standalone
adaptation. The paper's historical-inventory fusion is not reproduced here.

Sentinel-2 imagery is real, licensed cached data; OSM generator polygons are
weak references. Outside buffered polygons is explicitly assumed negative.
The prediction callable receives imagery features, never evaluation labels.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv
from orbitalpv.ground_research import (
    SegmentationAdapter,
    adaptive_andpi,
    benchmark_segmentation,
    supervised_segmentation_adapter,
)

directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
data = directory.parent / "ground_imagery/_data"
configuration = json.loads((data / "pv-sites.json").read_text())
samples = {}
for name in ("cestas", "tenerife"):
    site = opv.load_pv_site(
        **configuration[name], cache_dir=data, offline=True, assets=("scl", *opv.PV_SPECTRAL_BANDS)
    )
    samples[name] = opv.prepare_pv_training_sample(site, site_id=name, background_is_negative=True)

models = [
    supervised_segmentation_adapter([samples["cestas"]], method="logistic"),
    SegmentationAdapter("ANDPI standalone adaptation", adaptive_andpi),
]
report = benchmark_segmentation(models, [samples["tenerife"]])
reference = samples["tenerife"]
fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), constrained_layout=True)
axes[0].imshow(np.ma.masked_less(reference.labels, 0), cmap="Greys", vmin=0, vmax=1)
axes[0].set_title("OSM weak reference")
for ax, model, row in zip(axes[1:], models, report["results"], strict=True):
    ax.imshow(model.predict(reference.features).mask, cmap="Greys", vmin=0, vmax=1)
    ax.set_title(f"{model.name}\nF1 {row['f1']:.3f}; IoU {row['iou']:.3f}", fontsize=9)
    print(
        {
            key: row[key]
            for key in ("model", "precision", "recall", "f1", "iou", "relative_area_bias")
        }
    )
for ax in axes:
    ax.set_axis_off()
fig.suptitle("Real Tenerife image; geographic transfer and weak-label agreement")
fig.text(
    0.5,
    -0.03,
    "Copernicus Sentinel data · © OpenStreetMap contributors (ODbL)",
    ha="center",
    fontsize=8,
)
plt.show()
