"""Reproduce the offline delivery study and its evidence manifest."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    path = ROOT / "examples/space_business/plot_sbsp_delivery.py"
    spec = importlib.util.spec_from_file_location("delivery_example", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.study()
    out = ROOT / "outputs/sbsp_delivery"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    result.to_csv(out / "scenarios.csv", index=False)
    result.to_parquet(out / "events.parquet", index=False)
    module.plot_results(result).savefig(out / "figures/delivery.png", dpi=150)
    config = {
        "hours": 8760,
        "load_w": 100e6,
        "energy_target_wh": 876000e6,
        "evidence": "advertised targets; constructed profiles and assumed efficiencies",
        "seed": None,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    data = ROOT / "examples/space_business/_data/sbsp_delivery.csv"
    manifest = json.loads((data.parent / "sbsp_provenance.json").read_text())
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (data, path)
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    selected = result[result.scenario == "energy_surplus_interrupted"].to_dict("records")
    (out / "metrics.json").write_text(json.dumps(selected, indent=2) + "\n")
    (out / "logs.jsonl").write_text(
        json.dumps({"event": "completed", "scenarios": len(result)}) + "\n"
    )


if __name__ == "__main__":
    run()
