"""
Budgeting solar-array energy for a DRAGO-2 imaging session
==========================================================

How much solar-array energy should a mission planner reserve for the camera?
The IAC's `ALISIO-1 instrument sheet
<https://www.iac.es/system/files/documents/2023-09/ALISIO.pdf>`_ specifies
DRAGO-2 power below 5.5 W. Use 5.5 W as the design ceiling while imaging.
The first-observation composites illustrate what the camera produces in
:ref:`sphx_glr_gallery_ground_imagery_plot_alisio_canary_islands.py`.

This scenario covers active camera energy only. The operating times, 80%
end-to-end efficiency and 30-minute collection window are planning assumptions.
Spacecraft housekeeping, standby and downlink loads require separate budgets.
"""

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv

# %%
# Multiply camera power by active hours. To replace that energy from the array,
# divide by the assumed efficiency from array output to camera input. Average
# array power over the collection window follows by dividing energy by hours.

camera_limit_w = opv.AlisioConnector.DRAGO2_POWER_CEILING_W
efficiency = 0.80
collection_window_min = 30
active_minutes = np.array([1, 5, 10, 15, 20])
camera_energy_wh = camera_limit_w * active_minutes / 60
array_energy_wh = camera_energy_wh / efficiency
mean_array_power_w = array_energy_wh / (collection_window_min / 60)

for minutes, camera, array, power in zip(
    active_minutes, camera_energy_wh, array_energy_wh, mean_array_power_w, strict=True
):
    print(f"{minutes:2} min | camera {camera:.3f} Wh | array {array:.3f} Wh | mean {power:.2f} W")

fig, ax = plt.subplots(figsize=(7.2, 4.2), layout="constrained")
ax.plot(active_minutes, array_energy_wh, "o-", label="At solar-array output (80% efficiency)")
ax.plot(active_minutes, camera_energy_wh, "s--", label="At camera input (5.5 W ceiling)")
ax.set(
    xlabel="Assumed camera active time (min)",
    ylabel="Energy allocation (Wh)",
    title="DRAGO-2 imaging energy budget",
    xticks=active_minutes,
    ylim=(0, None),
)
ax.legend()
ax.grid(axis="y", alpha=0.25)
plt.show()
