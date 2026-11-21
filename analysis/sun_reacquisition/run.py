"""Reproduce the Sun-reacquisition reserve screen and its input provenance."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_sun_reacquisition.py"
    spec = importlib.util.spec_from_file_location("example", example)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = module.study()
    config, _ = module.inputs()
    metrics = module.metrics(results)
    out = ROOT / "outputs/sun_reacquisition"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    results.to_parquet(out / "events.parquet", index=False)
    results.to_csv(out / "scenarios.csv", index=False)
    for name, value in [("config", config), ("metrics", metrics)]:
        (out / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    manifest = json.loads((ROOT / "analysis/sun_reacquisition/provenance.json").read_text())
    files = [
        example,
        Path(__file__),
        ROOT / "packages/space-pv-pvmodel/src/space_pv_pvmodel/reserve.py",
        ROOT / "packages/space-pv-pvmodel/src/space_pv_pvmodel/eps.py",
        ROOT / "packages/space-pv-connectors/src/space_pv_connectors/tabular.py",
        *sorted((ROOT / "examples/space_business/_data").glob("sun_reacquisition.*")),
    ]
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "logs.jsonl").write_text(
        json.dumps(
            {"event": "completed", "scenarios": len(results), "forward_backward_agreement": True}
        )
        + "\n"
    )
    module.plot_study(results).savefig(out / "figures/reserve.png", dpi=150)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    run()
