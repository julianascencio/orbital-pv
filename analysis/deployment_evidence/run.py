"""Run deterministic deployment evidence screening and sample-size sensitivity."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_deployment_evidence.py"
    spec = importlib.util.spec_from_file_location("deployment_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evidence, plans = module.study()
    out = ROOT / "outputs/deployment_evidence"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    evidence.to_csv(out / "evidence.csv", index=False)
    plans.to_csv(out / "plans.csv", index=False)
    evidence.to_parquet(out / "events.parquet", index=False)
    module.plot_study(evidence, plans).savefig(out / "figures/evidence.png", dpi=150)
    config = {"confidence": 0.95, "seed": None, "data_kind": "synthetic one-shot trials"}
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    data = ROOT / "examples/space_business/_data/deployment_trials.csv"
    manifest = json.loads((data.parent / "deployment_provenance.json").read_text())
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (data, example)
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "metrics.json").write_text(
        json.dumps(
            {"evidence": evidence.to_dict("records"), "plans": plans.to_dict("records")}, indent=2
        )
        + "\n"
    )
    (out / "logs.jsonl").write_text(json.dumps({"event": "completed", "plans": len(plans)}) + "\n")


if __name__ == "__main__":
    run()
