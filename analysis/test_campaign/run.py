"""Write reproducible test-campaign planning artifacts."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_test_campaign.py"
    spec = importlib.util.spec_from_file_location("example", example)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result, matrix, frontier, sensitivity = module.study()
    out = ROOT / "outputs/test_campaign"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    matrix.to_csv(out / "planned_matrix.csv", index=False)
    frontier.to_parquet(out / "events.parquet", index=False)
    (out / "metrics.json").write_text(
        json.dumps({"base": result, "sensitivity": sensitivity}, indent=2)
    )
    (out / "config.json").write_text(
        json.dumps({"budget_h": 8, "budget_sweep_h": list(range(11)), "seed": None})
    )
    manifest = json.loads((ROOT / "analysis/test_campaign/provenance.json").read_text())
    files = [
        example,
        Path(__file__),
        ROOT / "packages/space-pv-analytics/src/space_pv_analytics/campaign.py",
        *sorted((ROOT / "examples/space_business/_data").glob("campaign_*.csv")),
    ]
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "logs.jsonl").write_text(json.dumps({"event": "completed", "scenarios": 12}) + "\n")
    module.plot_study(frontier).savefig(out / "figures/frontier.png", dpi=150)
    print(result)
    print(sensitivity)


if __name__ == "__main__":
    run()
