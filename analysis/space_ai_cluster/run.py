"""Export the pinned paper benchmark and synthetic compute sensitivities."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path

from orbitalpv.space_ai import load_space_ai_evidence
from orbitalpv.space_ai_analysis import space_ai_trade_study


def run(output: Path, input_path: Path | None = None) -> None:
    evidence = load_space_ai_evidence(input_path)
    raw = (
        input_path.read_bytes()
        if input_path
        else files("orbitalpv").joinpath("_data/space_ai_2511_19468v2.json").read_bytes()
    )
    tables = space_ai_trade_study(evidence)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output / f"{name}.csv", index=False, float_format="%.10g")
    provenance = {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "evidence": evidence,
        "table_rows": {name: len(frame) for name, frame in tables.items()},
        "limitations": "Screening only. No J2 control, SEE transport, end-to-end training performance or full economic feasibility model.",
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        tables["compute_screen"][
            ["scenario", "sustainable_compute_kw", "launch_only_energy_cost_parity_usd_kg"]
        ].to_string(index=False)
    )
    print(f"Wrote {len(tables)} reproducible tables to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/space_ai_cluster"))
    parser.add_argument("--input", type=Path, help="Optional modified evidence/scenario JSON")
    args = parser.parse_args()
    run(args.output, args.input)
