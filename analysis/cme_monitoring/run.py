"""Run the pinned research forecast study with reproducibility artifacts."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_cme_monitoring.py"
    spec = importlib.util.spec_from_file_location("cme_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results, windows = module.study()
    out = ROOT / "outputs/cme_monitoring"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "results.csv", index=False)
    results.to_parquet(out / "events.parquet", index=False)
    for i, frame in enumerate(windows.values()):
        frame.to_csv(out / f"windows_{i}.csv", index=False)
    module.plot_study(results, windows).savefig(out / "figures/windows.png", dpi=150)
    config = {
        "as_of_utc": module.AS_OF,
        "missing_bound_hours": [6, 12, 24],
        "midpoint_halfwidth_hours": 7,
        "cadences_s": [60, 600],
        "bytes_per_sample": 256,
        "seed": None,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    (out / "metrics.json").write_text(json.dumps(results.to_dict("records"), indent=2) + "\n")
    manifest = json.loads((ROOT / "analysis/cme_monitoring/provenance.json").read_text())
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            example,
            ROOT / "examples/space_business/_data/cme_arrival_forecasts.csv",
            ROOT / "packages/space-pv-analytics/src/space_pv_analytics/monitoring_windows.py",
            Path(__file__),
        ]
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "logs.jsonl").write_text(
        json.dumps({"event": "completed", "scenarios": len(results)}) + "\n"
    )
    print(results.to_string(index=False))


if __name__ == "__main__":
    run()
