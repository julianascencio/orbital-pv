"""Persist the Mars pointing study and its reproducibility manifest."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    example = ROOT / "examples/space_business/plot_mars_pointing.py"
    spec = importlib.util.spec_from_file_location("mars_pointing_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frame, sensitivity = module.study()
    out = ROOT / "outputs/mars_pointing"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "seasonal_power.csv", index=False)
    frame.to_parquet(out / "events.parquet", index=False)
    sensitivity.to_csv(out / "sensitivity.csv", index=False)
    module.plot_results(frame, sensitivity).savefig(out / "figures/pointing.png", dpi=150)
    (out / "config.json").write_text(json.dumps(module.configuration(), indent=2) + "\n")
    (out / "metrics.json").write_text(
        json.dumps(module.metrics(frame, sensitivity), indent=2) + "\n"
    )
    provenance = ROOT / "examples/space_business/_data/mars_pointing_provenance.json"
    manifest = json.loads(provenance.read_text())
    inputs = [
        example,
        provenance,
        provenance.with_name("mars_pointing.json"),
        ROOT / "packages/space-pv-pvmodel/src/space_pv_pvmodel/pointing.py",
        ROOT / "packages/space-pv-space-env/src/space_pv_space_env/mars.py",
        ROOT / "packages/space-pv-space-env/src/space_pv_space_env/solar.py",
    ]
    manifest["sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "logs.jsonl").write_text(
        json.dumps({"event": "completed", "samples": len(frame), "scenarios": len(sensitivity)})
        + "\n"
    )


if __name__ == "__main__":
    run()
