"""Execute the offline cable study and retain reproducibility artifacts."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_lunar_dc_distribution.py"
    spec = importlib.util.spec_from_file_location("cable_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = module.study()
    out = ROOT / "outputs/lunar_dc_distribution"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "results.csv", index=False)
    results.to_parquet(out / "events.parquet", index=False)
    module.plot_results(results).savefig(out / "figures/cable.png", dpi=140)
    data = ROOT / "examples/space_business/_data/lunar_dc_material.csv"
    provenance = json.loads((ROOT / "analysis/lunar_dc_distribution/provenance.json").read_text())
    provenance["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            data,
            example,
            ROOT / "packages/space-pv-pvmodel/src/space_pv_pvmodel/distribution.py",
        )
    }
    (out / "input_manifest.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (out / "config.json").write_text(
        json.dumps(
            {
                "input_csv": data.read_text(),
                "voltages_v": [400, 1000, 3000, 10000],
                "areas_mm2": [1, 4, 10],
                "resistance_multipliers": [1, 1.5, 2],
            },
            indent=2,
        )
        + "\n"
    )
    (out / "metrics.json").write_text(
        json.dumps(
            {
                "cases": len(results),
                "voltage_criterion_pass": int(results.voltage_criterion_pass.sum()),
            },
            indent=2,
        )
        + "\n"
    )
    (out / "logs.jsonl").write_text(
        json.dumps({"event": "completed", "cases": len(results)}) + "\n"
    )
    print(results[results.resistance_multiplier == 1].to_string(index=False))


if __name__ == "__main__":
    run()
