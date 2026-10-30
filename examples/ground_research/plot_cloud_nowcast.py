"""
Classical cloud optical-flow nowcast
====================================

A SYNTHETIC transported-cloud field isolates motion estimation. It is not a
real weather skill benchmark. The method accepts dimensionless retrieved
clear-sky-index grids, not raw satellite radiance or cloud-class labels.
Missing incoming boundaries remain unknown. Future GHI uses the corresponding
future clear-sky irradiance in W/m².
"""

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter, shift

from orbitalpv.ground_forecasting import (
    clear_sky_persistence,
    evaluate_irradiance_forecast,
    forecast_irradiance,
)

rng = np.random.default_rng(42)
texture = gaussian_filter(rng.random((80, 80)), 2)
previous = 0.2 + 0.75 * (texture - texture.min()) / (texture.max() - texture.min())
current = shift(previous, (0.5, 1.4), order=1, mode="constant", cval=np.nan)
leads = [0, 5, 15]
clear_sky = np.stack([np.full(current.shape, 700 + 2 * lead) for lead in leads])
forecast = forecast_irradiance(
    previous,
    current,
    clear_sky,
    minutes_between=5,
    lead_minutes=leads,
    source="synthetic controlled cloud motion",
    license_name="CC0",
    max_shift_pixels=8,
)
persistence = clear_sky_persistence(current * 700, 700, clear_sky)
truth = shift(current, (1.5, 4.2), order=1, mode="constant", cval=np.nan) * clear_sky[-1]
metrics = evaluate_irradiance_forecast(forecast.ghi_wm2[-1], truth, persistence=persistence[-1])
fig, axes = plt.subplots(1, 3, figsize=(11, 4), constrained_layout=True)
for ax, values, title in zip(
    axes,
    (truth, persistence[-1], forecast.ghi_wm2[-1]),
    ("Synthetic truth at +15 min", "Clear-sky persistence", "Lucas-Kanade optical flow"),
    strict=True,
):
    image = ax.imshow(values, cmap="viridis", vmin=0, vmax=800)
    ax.set_title(title, fontsize=10)
    ax.set_axis_off()
fig.colorbar(image, ax=axes, shrink=0.7, label="Scenario GHI (W/m²)")
print(metrics)
print("Synthetic advection skill cannot be used as a real-world forecast accuracy claim.")
plt.show()
