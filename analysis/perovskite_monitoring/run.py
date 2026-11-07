"""Run the modeled perovskite monitoring campaign study offline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(output: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "monitoring_example", ROOT / "examples/space_business/plot_perovskite_monitoring.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load gallery example")
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    results = example.campaign_table()
    output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / "campaigns.csv", index=False)
    example.plot_campaign(results).savefig(output / "campaigns.png", dpi=160)
    inputs = ROOT / "examples/space_business/_data/monitoring_noise_cases.csv"
    provenance = json.loads((inputs.parent / "monitoring_provenance.json").read_text())
    (output / "input_manifest.json").write_text(
        json.dumps(
            {
                **provenance,
                "input_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
                "units": {
                    "time": "elapsed days",
                    "covariance": "natural-log power squared",
                    "slope": "year^-1; 365.25 days/year",
                    "loss": "fraction",
                },
                "time_frame": "relative campaign time; no ephemeris or UTC conversion",
            },
            indent=2,
        )
        + "\n"
    )
    reference = results[results.duration_days >= 364].to_dict("records")
    (output / "summary.json").write_text(
        json.dumps(
            {
                "evidence": "modeled design; no measured OrigamiSat-2 data",
                "cases": len(results),
                "long_campaign_cases": reference,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/perovskite_monitoring"))
    run(parser.parse_args().output)
