"""Run combined-stress evidence study and write reproducibility artifacts."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_combined_stress.py"
    spec = importlib.util.spec_from_file_location("stress_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result, arms, sensitivity = module.study()
    out = ROOT / "outputs/combined_stress"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    arms.to_csv(out / "arms.csv", index=False)
    sensitivity.to_csv(out / "sensitivity.csv", index=False)
    sensitivity.to_parquet(out / "events.parquet", index=False)
    module.plot_study(result, arms, sensitivity).savefig(out / "figures/interaction.png", dpi=150)
    (out / "metrics.json").write_text(
        json.dumps({"base": result, "sensitivity": sensitivity.to_dict("records")}, indent=2) + "\n"
    )
    (out / "config.json").write_text(
        json.dumps(
            {
                "seed": 1711,
                "bootstrap_samples": 4000,
                "confidence": 0.95,
                "combined_retention": [0.84, 0.90, 0.931 / 0.995, 0.97],
            },
            indent=2,
        )
        + "\n"
    )
    manifest = json.loads((ROOT / "analysis/combined_stress/provenance.json").read_text())
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            example,
            ROOT / "examples/space_business/_data/combined_stress.csv",
            ROOT / "packages/space-pv-analytics/src/space_pv_analytics/stress.py",
            Path(__file__),
        ]
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "logs.jsonl").write_text(
        json.dumps({"event": "completed", "samples": 24, "scenarios": 4}) + "\n"
    )
    print(result)


if __name__ == "__main__":
    run()
