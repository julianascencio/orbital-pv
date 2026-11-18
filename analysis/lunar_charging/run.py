"""Run the charging study and preserve provenance, metrics and plots."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_lunar_charging.py"
    spec = importlib.util.spec_from_file_location("charging_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results, traces, schedules = module.study()
    out = ROOT / "outputs/lunar_charging"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "results.csv", index=False)
    results.to_parquet(out / "events.parquet", index=False)
    schedules["scheduled"].to_csv(out / "schedule.csv", index=False)
    module.plot_study(results, traces).savefig(out / "figures/charging.png", dpi=150)
    metrics = results.to_dict("records")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    config = {
        "slot_hours": 1,
        "horizon_hours": 6,
        "efficiencies": [0.6, 0.8, 1],
        "pv_w": [500, 700, 900],
        "base_load_w": 100,
        "battery_wh": 2000,
        "initial_soc": 0.8,
        "minimum_soc": 0.2,
        "maximum_soc": 0.95,
        "charge_efficiency": 0.95,
        "discharge_efficiency": 0.95,
        "max_charge_w": 500,
        "max_discharge_w": 1000,
        "seed": None,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    manifest = json.loads((ROOT / "analysis/lunar_charging/provenance.json").read_text())
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            example,
            ROOT / "examples/space_business/_data/lunar_charging.csv",
            ROOT / "packages/space-pv-analytics/src/space_pv_analytics/charging.py",
            Path(__file__),
        ]
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "logs.jsonl").write_text(
        json.dumps({"event": "completed", "cases": len(results)}) + "\n"
    )
    print(results.to_string(index=False))


if __name__ == "__main__":
    run()
