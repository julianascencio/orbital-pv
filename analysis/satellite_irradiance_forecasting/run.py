"""Irradiance comparison on an explicitly synthetic cloud-advection scenario."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter, shift

from orbitalpv.ground_forecasting import (
    blend_irradiance_forecasts,
    clear_sky_persistence,
    evaluate_irradiance_forecast,
    forecast_irradiance,
)


def run(output: Path, *, seed: int = 42) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Choose an empty analysis output directory")
    # Engineered scenario isolates advection; cannot estimate real satellite accuracy.
    rng = np.random.default_rng(seed)
    texture = gaussian_filter(rng.random((96, 96)), 2)
    previous = 0.25 + 0.7 * (texture - texture.min()) / (texture.max() - texture.min())
    displacement = (0.6, 1.4)
    current = shift(previous, displacement, order=1, mode="constant", cval=np.nan)
    leads = [0, 5, 10, 20, 30]
    clear = np.stack([np.full(current.shape, 700 + lead * 2) for lead in leads])
    truth = np.stack(
        [
            shift(
                current,
                tuple(value * lead / 5 for value in displacement),
                order=1,
                mode="constant",
                cval=np.nan,
            )
            * sky
            for lead, sky in zip(leads, clear, strict=True)
        ]
    )
    persistence = clear_sky_persistence(current * 700, 700, clear)
    forecast = forecast_irradiance(
        previous,
        current,
        clear,
        minutes_between=5,
        lead_minutes=leads,
        source="synthetic frozen-cloud motion scenario",
        license_name="CC0",
        max_shift_pixels=10,
    )
    # Deliberately smoothed fictitious weather forecast, labelled as a scenario.
    weather = np.stack(
        [gaussian_filter(np.nan_to_num(t, nan=np.nanmean(t)), 4) + 20 for t in truth]
    )
    fused = blend_irradiance_forecasts(
        forecast.ghi_wm2,
        weather,
        lead_minutes=leads,
        forecast_origin="2026-06-01T12:00Z",
        weather_issue_time="2026-06-01T06:00Z",
        transition_minutes=60,
    )
    metrics = {
        name: [
            dict(
                lead_minutes=lead,
                **evaluate_irradiance_forecast(values[i], truth[i], persistence=persistence[i]),
            )
            for i, lead in enumerate(leads)
        ]
        for name, values in (("optical_flow", forecast.ghi_wm2), ("fusion_scenario", fused))
    }
    report = {
        "data_kind": "synthetic algorithm scenario; no real forecast skill claim",
        "seed": seed,
        "known_displacement_pixels_per_5_minutes": displacement,
        "method": forecast.metadata,
        "weather_input": "synthetic smoothed future field used ONLY as a controlled illustration, not an operational weather hindcast",
        "metrics": metrics,
        "motion_diagnostics": forecast.motion.quality,
        "real_data_next_step": "Use GOES DSR retrieval or calibrated SEVIRI irradiance, retain geolocation/DQF/acquisition times, use contemporaneous issued weather forecasts and independent irradiance observations",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    np.savez_compressed(
        output / "synthetic_scenario.npz",
        previous_index=previous,
        current_index=current,
        future_clear_sky_wm2=clear,
        truth_ghi_wm2=truth,
        optical_flow_ghi_wm2=forecast.ghi_wm2.filled(np.nan),
        persistence_ghi_wm2=persistence.filled(np.nan),
        fusion_ghi_wm2=fused.filled(np.nan),
    )
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    for ax, values, title in zip(
        axes,
        (truth[-1], persistence[-1], forecast.ghi_wm2[-1]),
        ("Synthetic truth at +30 min", "Clear-sky persistence", "Lucas-Kanade cloud advection"),
        strict=True,
    ):
        image = ax.imshow(values, vmin=0, vmax=900, cmap="viridis")
        ax.set_title(title, fontsize=10)
        ax.set_axis_off()
    fig.colorbar(image, ax=axes, shrink=0.7, label="Scenario GHI (W/m²)")
    fig.savefig(output / "synthetic_nowcast.png", dpi=160)
    plt.close(fig)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/satellite_irradiance_forecasting")
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(run(args.output, seed=args.seed)["metrics"], indent=2))
