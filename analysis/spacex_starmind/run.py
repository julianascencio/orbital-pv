"""Reproduce the SpaceX-inspired orbital-compute screening case offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv.orbital_compute import (
    OrbitalComputeSpec,
    deployment_screen,
    screen_orbital_compute,
    simulate_orbital_compute,
)
from orbitalpv.physics import BatterySpec

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "examples/space_business/_data/spacex_starmind.json"


def run(output: Path, input_path: Path = INPUT) -> None:
    data = json.loads(input_path.read_text())
    baseline = dict(data["baseline"])
    battery = BatterySpec(**baseline.pop("battery"))
    base = OrbitalComputeSpec(**baseline, battery=battery)
    dispatch = dict(data["dispatch"])
    report_cycles = dispatch.pop("report_last_cycles")
    if not 1 <= report_cycles <= dispatch["cycles"]:
        raise ValueError("report_last_cycles must be between 1 and cycles")
    output.mkdir(parents=True, exist_ok=True)
    rows, traces, fleets, policies = [], [], [], []
    for scenario in data["scenarios"]:
        spec = replace(
            base,
            **scenario["changes"],
            battery=replace(base.battery, **scenario.get("battery_changes", {})),
        )
        screen = screen_orbital_compute(spec)
        for policy in ("greedy", "continuous_cap"):
            policy_trace = simulate_orbital_compute(spec, **dispatch, dispatch_policy=policy)
            window = policy_trace[policy_trace.cycle >= dispatch["cycles"] - report_cycles]
            policies.append(
                {
                    "scenario": scenario["name"],
                    "policy": policy,
                    "served_compute_kw": float(
                        (window.served_compute_w * window.duration_h).sum()
                        / window.duration_h.sum()
                        / 1000
                    ),
                    "platform_unserved_kwh": float(
                        (
                            (spec.platform_load_w - window.served_platform_w) * window.duration_h
                        ).sum()
                        / 1000
                    ),
                    "rejected_compute_kwh": float(window.rejected_compute_wh.sum() / 1000),
                    "report_duration_h": float(window.duration_h.sum()),
                    "soc_change": float(window.soc_end.iloc[-1] - window.soc_start.iloc[0]),
                }
            )
        trace = simulate_orbital_compute(spec, **dispatch)
        tail = trace[trace.cycle >= dispatch["cycles"] - report_cycles].copy()
        hours = tail.duration_h.sum()
        requested_wh = (tail.requested_compute_w * tail.duration_h).sum()
        served_wh = (tail.served_compute_w * tail.duration_h).sum()
        rows.append(
            {
                "scenario": scenario["name"],
                **screen,
                "burst_served_compute_kw": served_wh / hours / 1000,
                "burst_served_energy_fraction": served_wh / requested_wh,
                "burst_unserved_compute_kwh": tail.unserved_compute_wh.sum() / 1000,
                "report_duration_h": hours,
                "minimum_soc": tail.soc_end.min(),
                "final_soc": tail.soc_end.iloc[-1],
                "report_soc_change": tail.soc_end.iloc[-1] - tail.soc_start.iloc[0],
                "platform_unserved_kwh": (
                    (spec.platform_load_w - tail.served_platform_w) * tail.duration_h
                ).sum()
                / 1000,
                "max_power_balance_error_w": trace.power_balance_error_w.abs().max(),
                "max_eps_battery_heat_kw": trace.modeled_eps_battery_heat_w.max() / 1000,
                "thermal_allowance_exceeded": bool(trace.thermal_allowance_exceeded.any()),
            }
        )
        tail.insert(0, "scenario", scenario["name"])
        traces.append(tail)
        # Capacity is firm service, capped at the published average target.
        firm_kw = min(float(screen["sustainable_compute_kw"]), spec.average_compute_w / 1000)
        fleets.append(
            {
                "scenario": scenario["name"],
                **deployment_screen(
                    **{**data["deployment"], **scenario.get("deployment_changes", {})},
                    array_area_m2=spec.pv_area_m2,
                    continuous_compute_kw=firm_kw,
                ),
            }
        )
    sensitivity = [
        {
            "beta_deg": beta,
            "pv_area_m2": area,
            **screen_orbital_compute(replace(base, beta_angle_deg=beta, pv_area_m2=area)),
        }
        for beta in np.linspace(0, 90, 19)
        for area in (800, 1000, 1200, 1600)
    ]
    launch_sweep = [
        {
            "launches_per_year": launches,
            **deployment_screen(
                **{**data["deployment"], "launches_per_year": launches},
                array_area_m2=base.pv_area_m2,
                continuous_compute_kw=min(
                    float(screen_orbital_compute(base)["sustainable_compute_kw"]),
                    base.average_compute_w / 1000,
                ),
            ),
        }
        for launches in (100, 500, 1000, 2000, 5000, 8000, 10000)
    ]
    pd.DataFrame(policies).to_csv(output / "dispatch_policies.csv", index=False)
    pd.DataFrame(rows).to_csv(output / "scenarios.csv", index=False)
    pd.concat(traces, ignore_index=True).to_csv(output / "dispatch.csv", index=False)
    pd.DataFrame(fleets).to_csv(output / "deployment.csv", index=False)
    pd.DataFrame(sensitivity).to_csv(output / "sensitivity.csv", index=False)
    pd.DataFrame(launch_sweep).to_csv(output / "launch_sweep.csv", index=False)
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                "inputs": data,
                "interpretation": "Synthetic screening, not SpaceX telemetry, deployment forecast or AI throughput benchmark.",
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    print(
        pd.DataFrame(rows)[
            [
                "scenario",
                "sustainable_compute_kw",
                "burst_served_compute_kw",
                "average_target_feasible",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/spacex_starmind"))
    parser.add_argument("--input", type=Path, default=INPUT)
    args = parser.parse_args()
    run(args.output, args.input)
