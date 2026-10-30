"""
Find the current-limiting subcell in a tandem
=============================================

The illustrative spectrum is a 5772 K blackbody shape normalized to 1361 W/m²
over this wavelength range; it is not a measured AM0 reference. External EQEs
are referenced to the same incident light, preventing photon double counting.
"""

import matplotlib.pyplot as plt
import numpy as np

from orbitalpv import physics as opv

wavelength = np.linspace(280, 1800, 761)
metres = wavelength * 1e-9
spectrum = metres**-5 / np.expm1(6.62607015e-34 * 299792458 / (metres * 1.380649e-23 * 5772))
spectrum *= 1361 / np.trapezoid(spectrum, wavelength)

splits = np.arange(550, 851, 10)
currents = []
for split in splits:
    top = np.where((wavelength >= 350) & (wavelength < split), 0.85, 0)
    bottom = np.where((wavelength >= split) & (wavelength <= 1100), 0.85, 0)
    matched = opv.tandem_current_density(wavelength, spectrum, [top, bottom])
    currents.append([*matched.subcell_current_a_m2, matched.series_current_a_m2])
currents = np.asarray(currents)

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
axes[0].plot(wavelength, spectrum, color="tab:orange")
axes[0].set(
    xlabel="Wavelength [nm]", ylabel="Spectral irradiance [W m⁻² nm⁻¹]", title="Synthetic spectrum"
)
for index, label in enumerate(("Top subcell", "Bottom subcell", "Series-limiting current")):
    axes[1].plot(splits, currents[:, index], label=label)
axes[1].set(
    xlabel="Idealized EQE split wavelength [nm]",
    ylabel="Photocurrent density [A/m²]",
    title="Current matching, without an efficiency claim",
)
axes[1].legend(fontsize=8)
for axis in axes:
    axis.grid(alpha=0.25)
fig.tight_layout()
plt.show()
