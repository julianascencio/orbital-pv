"""Run with python -m orbitalpv.catalogue."""

import argparse
import json
from pathlib import Path

from .core import build_snapshot, stage_omm, validate_catalogue


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Satellite PV database: offline validation and exports"
    )
    parser.add_argument("--root", type=Path, help="Custom canonical data directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, required=True)
    stage = commands.add_parser("stage-omm")
    stage.add_argument("--input", type=Path, required=True)
    stage.add_argument("--source-id", required=True)
    stage.add_argument("--now", required=True)
    stage.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_snapshot(args.output, args.root)
    elif args.command == "stage-omm":
        rows = stage_omm(
            json.loads(args.input.read_text(encoding="utf-8")),
            source_id=args.source_id,
            now=args.now,
        )
        with args.output.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        result = {"staged_candidates": len(rows), "admitted": 0}
    else:
        result = validate_catalogue(args.root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
