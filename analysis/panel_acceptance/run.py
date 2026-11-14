"""Execute the offline repaired-panel study and record reproducible artifacts."""

import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_panel_acceptance.py"
    spec = importlib.util.spec_from_file_location("acceptance_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases, plans = module.study()
    out = ROOT / "outputs/panel_acceptance"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    cases.to_csv(out / "cases.csv", index=False)
    plans.to_csv(out / "plans.csv", index=False)
    cases.to_parquet(out / "events.parquet", index=False)
    module.plot_study(cases, plans).savefig(out / "figures/acceptance.png", dpi=150)
    config = {
        **module.CONFIG,
        "correlations": [0, 0.5, 0.9, 1],
        "planned_pair_counts": [1, 2, 4, 8, 16, 32, 64, 128],
        "seed": None,
        "data_kind": "hand-constructed synthetic paired Pmax, not flight data",
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    provenance_path = ROOT / "analysis/panel_acceptance/provenance.json"
    manifest = json.loads(provenance_path.read_text())
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            ROOT / "examples/space_business/_data/panel_acceptance.csv",
            example,
            Path(__file__),
            provenance_path,
            ROOT / "packages/space-pv-analytics/src/space_pv_analytics/acceptance.py",
        )
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    metrics = {"cases": cases.to_dict("records"), "plans": plans.to_dict("records")}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (out / "logs.jsonl").write_text(
        json.dumps(
            {
                "event": "completed",
                "time_utc": datetime.now(UTC).isoformat(),
                "cases": len(cases),
                "plans": len(plans),
            }
        )
        + "\n"
    )
    print(cases.to_string(index=False))


if __name__ == "__main__":
    run()
