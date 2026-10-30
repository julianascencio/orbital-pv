"""Validate thermal integration analytically or against explicitly supplied telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv import physics as opv


def run(output: Path, telemetry: Path | None = None) -> dict:
    """Write a numerical benchmark, or an observational comparison if CSV is given.

    Input CSV needs time_s, direct_solar_w_m2, observed_temperature_k; optional
    albedo_w_m2/earth_ir_w_m2 default to zero. The caller is responsible for
    sensor alignment, projected irradiance, and the effective surface parameters.
    """
    surface = opv.ThermalSurface(sink_temperature_k=0)
    if telemetry is None:
        time = np.arange(0.0, 7201.0, 30.0)
        coefficient = surface.ir_emissivity * 5.670374419e-8 * surface.radiating_area_m2
        reference = (320.0**-3 + 3 * coefficient * time / surface.heat_capacity_j_k) ** (-1 / 3)
        inputs = pd.DataFrame(
            {"time_s": time, "direct_solar_w_m2": 0.0, "observed_temperature_k": reference}
        )
        provenance = {"kind": "analytic dark-cooling benchmark", "flight_validation": False}
        efficiency = 0.0
        step = 1.0
    else:
        inputs = pd.read_csv(telemetry)
        required = {"time_s", "direct_solar_w_m2", "observed_temperature_k"}
        if not required.issubset(inputs):
            raise ValueError(f"telemetry CSV requires {sorted(required)}")
        provenance = {
            "kind": "user-supplied telemetry",
            "sha256": hashlib.sha256(telemetry.read_bytes()).hexdigest(),
            "filename": telemetry.name,
        }
        efficiency = 0.25
        step = 10.0
    observed = inputs.observed_temperature_k.to_numpy(float)
    if not np.all(np.isfinite(observed)) or np.any(observed <= 0):
        raise ValueError("reference temperatures must be finite and positive")
    model = opv.simulate_panel_thermal(
        inputs.time_s,
        inputs.direct_solar_w_m2,
        surface=surface,
        albedo_w_m2=inputs.get("albedo_w_m2", 0.0),
        earth_ir_w_m2=inputs.get("earth_ir_w_m2", 0.0),
        pv_efficiency=efficiency,
        initial_temperature_k=float(observed[0]),
        max_step_s=step,
    )
    model["reference_temperature_k"] = observed
    residual = model.temperature_k.to_numpy() - observed
    summary = {
        "provenance": provenance,
        "surface": asdict(surface),
        "max_step_s": step,
        "rmse_k": float(np.sqrt(np.mean(residual**2))),
        "maximum_absolute_error_k": float(np.max(np.abs(residual))),
        "maximum_energy_balance_error_j": float(np.max(np.abs(model.energy_balance_error_j))),
        "samples": len(model),
        "interpretation": "Default run verifies the integrator against an independent analytic solution; it is not flight validation.",
    }
    output.mkdir(parents=True, exist_ok=True)
    model.to_csv(output / "thermal_comparison.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/flight_thermal_validation"))
    parser.add_argument("--telemetry", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.output, arguments.telemetry), indent=2))
