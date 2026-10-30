"""Reproduce an explicitly illustrative spectrum/shielding/EOL thermal tradeoff."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv import physics as opv


def run(output: Path) -> dict:
    energy = np.geomspace(0.1, 10.0, 201)
    spectrum = energy**-1.4
    spectrum *= 1e12 / np.trapezoid(spectrum, energy)
    niel = 0.01 / np.sqrt(energy)
    response = opv.RadiationResponse(0.08, 1e12)
    surface = opv.ThermalSurface()
    rows = []
    for label, transmission in (
        ("unattenuated", np.ones_like(energy)),
        ("illustrative_attenuation", 1 - np.exp(-energy / 0.8)),
    ):
        exposure = opv.radiation_equivalent_fluence(
            energy,
            spectrum,
            niel,
            reference_niel_mev_cm2_g=0.01,
            shielding_transmission=transmission,
        )
        for year in range(6):
            equivalent = exposure.equivalent_fluence_cm2 * year
            retention = float(opv.retained_power_fraction(equivalent, response))
            # Optical changes below are declared sensitivity assumptions, not fitted data.
            aged = replace(
                surface,
                solar_absorptivity=0.9 + 0.2 * (1 - retention),
                ir_emissivity=0.85 - 0.1 * (1 - retention),
            )
            model = opv.simulate_panel_thermal(
                [0, 18_000],
                1361.0,
                surface=aged,
                earth_ir_w_m2=100,
                pv_efficiency=0.3 * retention,
                max_step_s=30,
            )
            rows.append(
                {
                    "case": label,
                    "year": year,
                    "equivalent_fluence_cm2": equivalent,
                    "retained_fraction": retention,
                    "temperature_k": float(model.temperature_k.iloc[-1]),
                    "pv_power_w": float(model.pv_power_w.iloc[-1]),
                }
            )
    table = pd.DataFrame(rows)
    summary = {
        "input_kind": "synthetic sensitivity study; no orbit-specific environment or qualified material calibration",
        "annual_integrated_fluence_cm2": 1e12,
        "response_assumption": asdict(response),
        "reference_niel_mev_cm2_g": 0.01,
        "surface": asdict(surface),
        "end_of_life": table[table.year == 5].to_dict(orient="records"),
        "interpretation": "Attenuation is supplied, not a shielding-transport calculation; thermal/optical feedback is an illustrative sensitivity.",
        "inspiration_doi": "10.1016/j.renene.2026.125716",
    }
    output.mkdir(parents=True, exist_ok=True)
    table.to_csv(output / "eol_tradeoffs.csv", index=False)
    pd.DataFrame(
        {"energy_mev": energy, "differential_fluence_cm2_mev": spectrum, "niel_mev_cm2_g": niel}
    ).to_csv(output / "spectrum.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/radiation_eol_tradeoffs"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
