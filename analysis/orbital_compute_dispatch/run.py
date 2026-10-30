"""Compare continuous and sunlight-preferred compute using the same energy demand."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from orbitalpv import physics as opv


def run(output: Path) -> dict:
    orbits = 8
    period_s = 5400.0
    time = np.arange(0, orbits * period_s + 60, 60)
    generation = np.where(time[:-1] % period_s < 0.6 * period_s, 45.0, 0.0)
    battery = opv.BatterySpec(
        25, initial_soc=0.8, minimum_soc=0.2, max_charge_w=30, max_discharge_w=30
    )
    radiator = opv.radiator_feasibility(
        38, area_m2=0.08, radiator_temperature_k=320, emissivity=0.9, absorbed_environment_w_m2=50
    )
    limit = float(radiator["available_heat_rejection_w"])
    baseline = opv.dispatch_power(
        time, generation, 16.0, battery=battery, maximum_served_power_w=limit
    )
    tasks = [opv.ComputeTask(12, i * period_s, (i + 1) * period_s, 30) for i in range(orbits)]
    scheduled, completion = opv.schedule_compute_workload(
        time,
        generation,
        8.0,
        battery=battery,
        tasks=tasks,
        compute_power_limit_w=30,
        thermal_power_limit_w=limit,
    )
    metrics = {}
    for label, trace in (("continuous", baseline), ("solar_preferred", scheduled)):
        soc = np.r_[battery.initial_soc, trace.soc_end]
        metrics[label] = {
            "minimum_soc": float(np.min(soc)),
            "battery_discharged_wh": float(np.sum(trace.discharge_w * trace.duration_h)),
            "unserved_load_wh": float(np.sum(trace.unserved_load_w * trace.duration_h)),
            "battery_cycle_damage": opv.battery_cycle_damage(
                soc, cycles_to_failure_at_full_depth=3000
            ),
            "maximum_balance_error_w": float(np.max(np.abs(trace.power_balance_error_w))),
        }
    summary = {
        "input_kind": "synthetic 90-minute orbit and declared component assumptions",
        "period_s": period_s,
        "sunlit_fraction": 0.6,
        "orbits": orbits,
        "battery": asdict(battery),
        "radiator": radiator,
        "requested_compute_wh": float(completion.requested_energy_wh.sum()),
        "completed_compute_wh": float(completion.completed_energy_wh.sum()),
        "missed_task_energy_wh": float(completion.unserved_energy_wh.sum()),
        "metrics": metrics,
        "interpretation": "Heuristic dispatch and steady radiator bound; no claim of optimality or commercial orbital-datacenter feasibility.",
        "inspiration_dois": [
            "10.1109/ACCESS.2026.3656399",
            "10.1016/j.asr.2026.06.093",
            "10.48550/arXiv.2604.27197",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(output / "continuous_dispatch.csv", index=False)
    scheduled.to_csv(output / "scheduled_dispatch.csv", index=False)
    completion.to_csv(output / "tasks.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/orbital_compute_dispatch"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
