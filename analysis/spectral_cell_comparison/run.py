"""Reproduce spectral photocurrent and tandem mismatch with explicit assumptions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv import physics as opv


def run(output: Path, spectrum_csv: Path | None = None) -> dict:
    if spectrum_csv is None:
        wavelength = np.linspace(280, 1800, 761)
        metres = wavelength * 1e-9
        irradiance = metres**-5 / np.expm1(
            6.62607015e-34 * 299792458 / (metres * 1.380649e-23 * 5772)
        )
        irradiance *= 1361 / np.trapezoid(irradiance, wavelength)
        provenance = {
            "kind": "5772 K blackbody shape normalized over 280-1800 nm; not a measured AM0 reference",
            "synthetic": True,
        }
    else:
        spectrum = pd.read_csv(spectrum_csv)
        wavelength = spectrum.wavelength_nm.to_numpy(float)
        irradiance = spectrum.spectral_irradiance_w_m2_nm.to_numpy(float)
        provenance = {
            "kind": "user-supplied spectrum",
            "sha256": hashlib.sha256(spectrum_csv.read_bytes()).hexdigest(),
        }
    single_eqe = np.where((wavelength >= 350) & (wavelength <= 1100), 0.85, 0)
    single_current = float(opv.spectral_photocurrent_density(wavelength, irradiance, single_eqe))
    records = []
    for split_nm in (600, 650, 700, 750, 800):
        top = np.where((wavelength >= 350) & (wavelength < split_nm), 0.85, 0)
        bottom = np.where((wavelength >= split_nm) & (wavelength <= 1100), 0.85, 0)
        result = opv.tandem_current_density(wavelength, irradiance, [top, bottom])
        records.append(
            {
                "split_wavelength_nm": split_nm,
                "top_current_a_m2": float(result.subcell_current_a_m2[0]),
                "bottom_current_a_m2": float(result.subcell_current_a_m2[1]),
                "series_current_a_m2": result.series_current_a_m2,
                "current_mismatch_fraction": result.current_mismatch_fraction,
            }
        )
    summary = {
        "spectrum": provenance,
        "eqe_kind": "illustrative idealized external EQE windows, not technology characterization",
        "integrated_irradiance_w_m2": float(np.trapezoid(irradiance, wavelength)),
        "single_junction_photocurrent_a_m2": single_current,
        "tandem_cases": records,
        "interpretation": "Photocurrent/current matching only; no voltage, fill-factor or efficiency ranking is inferred.",
        "inspiration_doi": "10.1038/s44172-026-00813-2",
    }
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"wavelength_nm": wavelength, "spectral_irradiance_w_m2_nm": irradiance}).to_csv(
        output / "spectrum.csv", index=False
    )
    pd.DataFrame(records).to_csv(output / "tandem_currents.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/spectral_cell_comparison"))
    parser.add_argument("--spectrum", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.spectrum), indent=2))
