"""
Expected PV power versus incidence angle
=========================================

A calibrated PV reference model is driven by AM0 irradiance and panel incidence.
This example uses the public ``orbitalpv`` API installed by ``pip install orbital-pv``.
"""

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv

aoi_deg = np.linspace(0.0, 90.0, 181)
cosine_aoi = np.cos(np.deg2rad(aoi_deg))
g_am0 = opv.am0_irradiance(opv.ASTRONOMICAL_UNIT_M)
g_effective = opv.effective_irradiance_w_m2(
    g_am0,
    1.0,
    cosine_aoi,
    optical_factor=0.96,
)

reference = opv.PvwattsReference(pdc0_w=30.0, gamma_pdc_per_c=-0.002)
power_w = opv.pvwatts_dc_space(g_effective, 45.0, reference)

fig, ax = plt.subplots()
ax.plot(aoi_deg, power_w)
ax.set(xlabel="Angle of incidence [deg]", ylabel="Expected DC power [W]")
ax.set_title("AM0 reference power versus panel incidence")
ax.grid(True, alpha=0.3)
plt.show()
