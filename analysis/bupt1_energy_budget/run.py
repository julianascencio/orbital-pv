"""Reconcile measured BUPT-1 electrical boundaries without inventing UTC or MPP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import orbitalpv as opv

ROOT = Path(__file__).resolve().parents[2]


def analyze(
    path: Path, *, time_min: str, time_max: str, source_timezone: str | None = None
) -> dict:
    frame = opv.load_bupt1_telemetry(
        path, time_min=time_min, time_max=time_max, source_timezone=source_timezone
    )
    source_metadata = frame.attrs.copy()
    # Ambiguous duplicate clocks are excluded, rather than averaged into invented
    # simultaneous measurements. Their missing interval remains visible.
    duplicates = frame.timestamp.duplicated(keep=False)
    clean = frame.loc[~duplicates].sort_values("timestamp").reset_index(drop=True)
    clean.attrs.update(source_metadata)
    budget = opv.measured_energy_budget(
        clean,
        battery_column="battery_source_signed_power_w",
        battery_discharge_sign=-1,
        max_gap_s=2,
    )
    input_comparison = opv.measured_energy_budget(
        clean, solar_column="pv_input_power_w", load_column="solar_bus_power_w", max_gap_s=2
    )
    # Currents are measurements; these rail voltages follow the authors' code
    # and are nominal assumptions, so the product remains a power estimate.
    clean["compute_power_estimate_w"] = 12.1 * (
        clean["atlas_a_current_a"] + clean["atlas_b_current_a"]
    ) + 5.1 * (clean["pi_a_current_a"] + clean["pi_b_current_a"])
    compute_comparison = opv.measured_energy_budget(
        clean, solar_column="compute_power_estimate_w", load_column="bus_power_w", max_gap_s=2
    )
    # Aggregate interval energies, not raw samples, into source-clock hours.
    # For the default one-second snapshot no interval crosses an hour except at
    # its final endpoint; intervals belong to the hour containing their start.
    intervals = budget.intervals[budget.intervals.accepted].copy()
    intervals["hour"] = pd.DatetimeIndex(intervals.start).floor("h")
    hourly = (
        intervals.groupby("hour")
        .agg(
            solar_wh=("solar_wh", "sum"),
            load_wh=("load_wh", "sum"),
            battery_discharge_wh=("battery_discharge_wh", "sum"),
            unexplained_balance_wh=("unexplained_balance_wh", "sum"),
            observed_seconds=("duration_s", "sum"),
        )
        .reset_index()
    )
    hourly["hour"] = hourly["hour"].astype(str)
    return {
        "source_paper": "https://arxiv.org/abs/2401.03435",
        "source_commit": source_metadata["source_commit"],
        "source_sha256": source_metadata["sha256"],
        "source_file": "CommonData-Telemetries/telemetry_all.csv.zip",
        "source_license": source_metadata["license"],
        "timestamp_basis": source_metadata["timestamp_basis"],
        "requested_start": time_min,
        "requested_stop_exclusive": time_max,
        "first_source_clock": str(clean.timestamp.min()),
        "last_source_clock": str(clean.timestamp.max()),
        "source_rows": len(frame),
        "ambiguous_duplicate_rows_excluded": int(duplicates.sum()),
        "median_native_cadence_s": float(
            np.median(np.diff(pd.DatetimeIndex(clean.timestamp).as_unit("ns").asi8) / 1e9)
        ),
        "bus_energy_budget": budget.summary,
        "input_output_comparison": input_comparison.summary,
        "compute_load_estimate": {
            "observed_energy_wh": compute_comparison.summary["solar_wh"],
            "nonzero_compute_current_rows": int((clean["compute_power_estimate_w"] != 0).sum()),
            "atlas_nominal_rail_v": 12.1,
            "raspberry_pi_nominal_rail_v": 5.1,
            "boundary": "Measured branch currents times source-code nominal rail voltages; estimated, not independently measured power",
        },
        "hourly_observed_energy": hourly.to_dict(orient="records"),
        "interpretation": [
            "MPPT input V*I and output-current times bus-voltage are different operating boundaries, neither available MPP.",
            "Battery discharge sign follows the original authors' plotted convention; independently verify it for other packets.",
            "The source does not specify its timezone. Default analysis uses relative source-clock durations without asserting UTC.",
            "An electrical balance residual is unexplained, not an attributed converter/thermal/aging loss.",
            "Only aggregate numerical results are committed. Download raw telemetry from its source; redistribution licence is unspecified.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--download", action="store_true", help="Download the pinned public source into --archive"
    )
    parser.add_argument("--start", default="2023-05-05 09:00:00")
    parser.add_argument("--stop", default="2023-05-05 15:00:00")
    parser.add_argument(
        "--source-timezone", default=None, help="Caller-established timezone; then use aware bounds"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/bupt1_energy_budget")
    args = parser.parse_args()
    if args.download:
        with opv.SatelliteCOTSConnector(timeout_s=120) as connector:
            connector.download(args.archive)
    summary = analyze(
        args.archive, time_min=args.start, time_max=args.stop, source_timezone=args.source_timezone
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
