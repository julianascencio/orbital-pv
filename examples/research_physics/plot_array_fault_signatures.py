"""
Distinguish mismatch, bypass and open-string I-V signatures
===========================================================

Two parallel strings contain three substrings each. These are constructed
circuit scenarios, not detected faults in a real spacecraft. The circuit model
uses a single diode, a constant bypass drop and ideal string blocking diodes.
"""

from dataclasses import replace

import matplotlib.pyplot as plt
import numpy as np

from orbitalpv import physics as opv

healthy = opv.PVSubstring(5.0, 20.0, diode_voltage_v=0.8)
shaded = replace(healthy, photocurrent_a=1.5, open_circuit_voltage_v=19.0)
cases = {
    "Healthy": [[healthy] * 3, [healthy] * 3],
    "One shaded substring": [[healthy, healthy, shaded], [healthy] * 3],
    "Open generating branch, bypass active": [
        [healthy, healthy, replace(healthy, fault="open")],
        [healthy] * 3,
    ],
    "Open string, no bypass": [
        [healthy, healthy, replace(healthy, fault="open", bypass_voltage_v=None)],
        [healthy] * 3,
    ],
}
voltage = np.linspace(0, 60, 1001)
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
for label, strings in cases.items():
    curve = opv.array_iv_curve(strings, voltage)
    axes[0].plot(curve.voltage_v, curve.current_a, label=label)
    axes[1].plot(curve.voltage_v, curve.power_w, label=label)
    print(f"{label}: sampled MPP {curve.attrs['pmp_w']:.1f} W")
axes[0].set(xlabel="Array voltage [V]", ylabel="Array current [A]", title="Current signatures")
axes[1].set(
    xlabel="Array voltage [V]", ylabel="Array power [W]", title="Mismatch changes the power curve"
)
for axis in axes:
    axis.grid(alpha=0.25)
axes[1].legend(fontsize=7)
fig.tight_layout()
plt.show()
