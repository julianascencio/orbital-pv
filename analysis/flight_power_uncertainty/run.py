"""Reproduce a chronological operating V/I forecast benchmark from real data."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

import orbitalpv as opv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "examples/flight_research/_data/flying_laptop_right_2018-02-01_03.csv"


def analyze(path: Path) -> tuple[dict, pd.DataFrame]:
    provenance = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    if sha256(path.read_bytes()).hexdigest() != provenance["snapshot_sha256"]:
        raise ValueError("Flight snapshot does not match its provenance checksum")
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    data = opv.make_lagged_vi_data(
        frame,
        lags=(0, 1, 2, 170, 176, 179),
        horizons=(1, 4, 10),
        cadence_s=30.15,
        cadence_tolerance_s=0.25,
    )
    training, calibration, evaluation = opv.chronological_forecast_split(
        data, training_stop="2018-02-02T00:00Z", calibration_stop="2018-02-03T00:00Z"
    )
    forecast = opv.fit_linear_vi_forecaster(training, ridge=1.0)
    predicted_cal = forecast.predict(calibration)
    predicted_eval = forecast.predict(evaluation)
    # Per-horizon residual scales use training observations only. These are not
    # calibrated uncertainty by themselves; the later partition supplies q.
    fitted_training = forecast.model.predict(training.features).reshape(training.targets.shape)
    scales = np.maximum((training.targets - fitted_training).std(axis=0), 1e-6)
    intervals = opv.calibrate_block_conformal_vi(
        calibration.targets,
        predicted_cal,
        origin_times=calibration.origin_times,
        target_end_times=calibration.target_end_times,
        trained_through=forecast.model.trained_through,
        scales=scales,
        block_size=20,
        coverage=0.9,
    )
    envelope = intervals.predict(predicted_eval, origin_times=evaluation.origin_times)
    truth = evaluation.targets[..., 0] * evaluation.targets[..., 1]
    baselines = {
        "persistence": opv.persistence_vi_forecast(evaluation),
        "seasonal_lag_180_steps": opv.seasonal_lag_vi_forecast(evaluation, period_steps=180),
        "multivariate_ridge": predicted_eval,
    }
    metrics = {}
    for name, predicted in baselines.items():
        power = predicted[..., 0] * predicted[..., 1]
        metrics[name] = {
            "voltage_mae_v": np.abs(predicted[..., 0] - evaluation.targets[..., 0])
            .mean(axis=0)
            .tolist(),
            "current_mae_a": np.abs(predicted[..., 1] - evaluation.targets[..., 1])
            .mean(axis=0)
            .tolist(),
            "power_mae_w": np.abs(power - truth).mean(axis=0).tolist(),
            "power_rmse_w": np.sqrt(((power - truth) ** 2).mean(axis=0)).tolist(),
        }
    summary = {
        "dataset_doi": provenance["dataset_doi"],
        "snapshot_sha256": provenance["snapshot_sha256"],
        "source_archive_sha256": provenance["sha256"],
        "license": "CC BY 4.0",
        "satellite": "Flying Laptop",
        "array": "right",
        "source_samples": len(frame),
        "source_windows": data.source_windows,
        "continuous_valid_windows": len(data.features),
        "training_windows": len(training.features),
        "calibration_windows": len(calibration.features),
        "evaluation_windows": len(evaluation.features),
        "training_labels_end": str(training.target_end_times[-1]),
        "calibration_origins_start": str(calibration.origin_times[0]),
        "calibration_labels_end": str(calibration.target_end_times[-1]),
        "evaluation_origins_start": str(evaluation.origin_times[0]),
        "horizon_source_steps": list(data.horizons),
        "nominal_cadence_s": data.cadence_s,
        "nominal_horizon_seconds": [h * data.cadence_s for h in data.horizons],
        "ridge": 1.0,
        "lags_source_steps": list(data.lags),
        "conformal": {
            "nominal_coverage": intervals.coverage,
            "block_size_records": intervals.block_size,
            "calibration_blocks": intervals.calibration_blocks,
            "discarded_tail_samples": intervals.discarded_tail_samples,
            "training_residual_scales_v_a_by_horizon": scales.tolist(),
            "quantile": intervals.quantile,
            **envelope.empirical_coverage(evaluation.targets),
        },
        "forecast_metrics_by_horizon": metrics,
        "interpretation": [
            "Predicts observed operating V/I, not available maximum power or a healthy reference.",
            "No measurements are interpolated and no energy is extrapolated through excluded gaps.",
            "180 source samples is an empirical 90.45-minute lag, not independently reconstructed orbit period.",
            "Finite-sample conformal coverage assumes exchangeable block scores; actual temporal coverage is measured, not guaranteed.",
            "A compact baseline implementation, not a reproduction of the complete 2026 paper.",
        ],
    }
    result = pd.DataFrame(
        {"origin": evaluation.origin_times, "last_target": evaluation.target_end_times}
    )
    for index, horizon in enumerate(data.horizons):
        result[f"actual_power_h{horizon}_w"] = truth[:, index]
        result[f"forecast_power_h{horizon}_w"] = envelope.power_prediction_w[:, index]
        result[f"lower_power_h{horizon}_w"] = envelope.power_lower_w[:, index]
        result[f"upper_power_h{horizon}_w"] = envelope.power_upper_w[:, index]
    return summary, result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/flight_power_uncertainty")
    args = parser.parse_args()
    summary, predictions = analyze(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    predictions.to_csv(args.output / "predictions.csv", index=False)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
