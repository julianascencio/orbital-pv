"""
Lunar inputs: measurements, computed geometry and NASA references
===================================================================

Replay the source-checked offline bundle. NASA SVS is a rendered illustration,
not measured solar flux or a quantitative validation target. The ephemerides
are calculated from JPL DE421; Diviner points are measured temperature bins.
Run analysis/lunar_surface_pv/fetch_inputs.py to refresh through all four public
connectors and recreate the subset with its source checksums.
"""

import matplotlib.pyplot as plt
from _lunar_analysis import analysis, version

from orbitalpv import lunar

observed = lunar.parse_diviner_pcp(
    (analysis.DATA / "diviner_subset.tab").read_bytes(),
    (analysis.DATA / "diviner_label.xml").read_bytes(),
    allow_subset=True,
)
observed["site"] = analysis.temperature_observations().site
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
axes[0].imshow(plt.imread(analysis.DATA / "svs_2026.jpg"))
axes[0].set_title("NASA SVS / Ernie Wright · qualitative reference")
axes[0].axis("off")
for site, values in observed.groupby("site"):
    axes[1].hist(
        values.temperature_k,
        bins=20,
        histtype="step",
        lw=1.8,
        label=f"Within 2 km box of point {site}",
    )
axes[1].set(
    xlabel="Bolometric brightness temperature [K]",
    ylabel="Observed spatial bins",
    title="Diviner: 2009-2020 cumulative source data",
)
axes[1].legend(fontsize=8)
print("Source records:", len(analysis.inputs()["sources"]))
print("Diviner records retained:", len(observed))
print("Frame:", lunar.LUNAR_FRAME)
print("OrbitalPV version:", version)
plt.show()
