"""
Lunar DC cable voltage and mass trade
=====================================

NASA's June 2026 logistics catalogue motivates a lunar PV utility decision:
which voltage and conductor area can deliver a 10 kW terminal load over 4 km?
These are modeled copper-like scenarios, not NASA/Astrobotic cable measurements.
High voltage trades conductor losses against insulation and converter risks
that this electrical screening model does not quantify.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from orbitalpv.data import load_table
from orbitalpv.physics import dc_cable_delivery


def study() -> pd.DataFrame:
    directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    inputs = load_table(directory / "_data/lunar_dc_material.csv").iloc[0].to_dict()
    rows = []
    for voltage in (400, 1000, 3000, 10000):
        for area in (1, 4, 10):
            for resistance_multiplier in (1.0, 1.5, 2.0):
                case = {
                    **inputs,
                    "resistivity_ohm_m": inputs["resistivity_ohm_m"] * resistance_multiplier,
                }
                rows.append(
                    {
                        "source_voltage_v": voltage,
                        "area_mm2": area,
                        "resistance_multiplier": resistance_multiplier,
                        **dc_cable_delivery(
                            **case, source_voltage_v=voltage, conductor_area_mm2=area
                        ),
                    }
                )
    return pd.DataFrame(rows)


def plot_results(results: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    base = results[results.resistance_multiplier == 1]
    for area, group in base.groupby("area_mm2"):
        axes[0].plot(
            group.source_voltage_v, group.cable_efficiency * 100, "o-", label=f"{area} mm²"
        )
        axes[1].scatter(
            group.conductor_mass_kg,
            group.receiving_voltage_v / group.source_voltage_v,
            label=f"{area} mm²",
        )
    axes[0].set(
        xscale="log",
        xlabel="Source voltage (V)",
        ylabel="Cable efficiency (%)",
        title="Gaps mean no DC equilibrium",
    )
    axes[1].axhline(0.9, color="black", linestyle=":", label="90% voltage criterion")
    axes[1].set(
        xlabel="Two-conductor mass only (kg)",
        ylabel="Receiving/source voltage",
        title="Insulation and packaging excluded",
    )
    for ax in axes:
        ax.legend(fontsize=8)
    fig.suptitle("Assumed 10 kW, 4 km lunar DC delivery — not flight performance")
    return fig


if __name__ == "__main__":
    results = study()
    print(results.to_string(index=False))
    plot_results(results)
    plt.show()
