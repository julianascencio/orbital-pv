"""Produce reproducible recovery-history scenario artifacts."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_recovery_history.py"
    spec = importlib.util.spec_from_file_location("example", example)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    traces, metrics = module.study()
    out = ROOT / "outputs/recovery_history"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    traces.to_parquet(out / "events.parquet", index=False)
    metrics.to_csv(out / "metrics.csv", index=False)
    (out / "metrics.json").write_text(metrics.to_json(orient="records", indent=2))
    module.plot_study(traces, metrics).savefig(out / "figures/recovery.png", dpi=150)
    (out / "config.json").write_text(
        json.dumps(
            {
                "permanent_retention": 0.98,
                "load_w": 1000,
                "recovery_multipliers": [0, 0.25, 0.5, 1, 2],
                "seed": None,
            }
        )
    )
    manifest = json.loads((ROOT / "analysis/recovery_history/provenance.json").read_text())
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            example,
            Path(__file__),
            ROOT / "examples/space_business/_data/recovery_history.csv",
            ROOT / "packages/space-pv-space-env/src/space_pv_space_env/recovery.py",
        ]
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "logs.jsonl").write_text(json.dumps({"event": "completed", "scenarios": 5}) + "\n")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    run()
