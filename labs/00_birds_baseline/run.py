"""Case 0 telemetry baseline using the public OrbitalPV API."""

from __future__ import annotations

import json
from dataclasses import asdict

import orbitalpv as opv


def main() -> None:
    telemetry = opv.make_demo_telemetry(seed=42)
    normalized = opv.add_robust_baseline(opv.add_power(telemetry))
    health = opv.daily_health(normalized)
    summary = opv.summarize_case0(normalized)

    print(json.dumps({"summary": asdict(summary)}, indent=2))
    print(f"anomaly_days={int(health['is_anomaly'].sum())}")


if __name__ == "__main__":
    main()
