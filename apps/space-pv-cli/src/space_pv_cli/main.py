from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from space_pv_analytics import add_power, add_robust_baseline, daily_health, summarize_case0
from space_pv_connectors import load_table, make_demo_telemetry, normalize_birds_like


def _case0(args: argparse.Namespace) -> int:
    if args.demo:
        frame = make_demo_telemetry(seed=args.seed)
    elif args.input:
        frame = normalize_birds_like(load_table(args.input))
    else:
        raise SystemExit("case0 requires --demo or --input PATH")

    result = add_robust_baseline(add_power(frame), reference_samples=args.reference_samples)
    health = daily_health(
        result,
        reference_samples=args.reference_samples,
        anomaly_threshold=args.anomaly_threshold,
    )
    summary = summarize_case0(result, anomaly_threshold=args.anomaly_threshold)
    payload = {"seed": args.seed, "summary": asdict(summary)}
    print(json.dumps(payload, indent=2))

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        health[health["is_anomaly"]].to_csv(output.with_suffix(".events.csv"), index=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="space-pv")
    sub = parser.add_subparsers(dest="command", required=True)

    case0 = sub.add_parser("case0", help="Run telemetry-only baseline analytics")
    source = case0.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="Use deterministic synthetic telemetry")
    source.add_argument("--input", type=str, help="CSV/XLSX/Parquet telemetry file")
    case0.add_argument("--seed", type=int, default=42)
    case0.add_argument("--reference-samples", type=int, default=500)
    case0.add_argument("--anomaly-threshold", type=float, default=5.0)
    case0.add_argument("--output", default="outputs/case0/metrics.json")
    case0.set_defaults(func=_case0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
