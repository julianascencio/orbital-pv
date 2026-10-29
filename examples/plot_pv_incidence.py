"""
Expected PV power versus incidence angle
=========================================

A calibrated PV reference model is driven by AM0 irradiance and panel incidence.
This is a broadband engineering baseline, not a multijunction spectral model.
"""

import matplotlib.pyplot as plt
import numpy as np

from space_pv_core.constants import ASTRONOMICAL_UNIT_M
from space_pv_pvmodel import PvwattsReference, effective_irradiance_w_m2, pvwatts_dc_space
from space_pv_space_env import am0_irradiance

aoi_deg = np.linspace(0.0, 90.0, 181)
cosine_aoi = np.cos(np.deg2rad(aoi_deg))
g_am0 = am0_irradiance(ASTRONOMICAL_UNIT_M)
g_effective = effective_irradiance_w_m2(g_am0, 1.0, cosine_aoi, optical_factor=0.96)

reference = PvwattsReference(pdc0_w=30.0, gamma_pdc_per_c=-0.002)
power_w = pvwatts_dc_space(g_effective, 45.0, reference)

fig, ax = plt.subplots()
ax.plot(aoi_deg, power_w)
ax.set(xlabel="Angle of incidence [deg]", ylabel="Expected DC power [W]")
ax.set_title("AM0 reference power versus panel incidence")
ax.grid(True, alpha=0.3)
plt.show()
