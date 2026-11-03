"""Reproduce an InSight energy hindcast from pinned measurements, entirely offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv import PvwattsReference, mars

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "examples/mars/_data"


def verify_sources(data: Path) -> dict:
    manifest = json.loads((data / "provenance.json").read_text())
    for name, record in manifest["files"].items():
        if hashlib.sha256((data / name).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"source checksum mismatch: {name}")
    return manifest


def align_opacity(
    target_sols: np.ndarray, observations: pd.DataFrame, max_gap_sols: float = 15.0
) -> tuple[np.ndarray, np.ndarray]:
    """Retrospective linear interpolation only inside bounded observation gaps.

    Future bracketing opacity is permitted: this is a hindcast, not a forecast.
    No extrapolation. Duplicate observation times are reduced by median.
    """
    if not np.isfinite(max_gap_sols) or max_gap_sols <= 0:
        raise ValueError("max_gap_sols must be finite and positive")
    observed = observations.groupby("sol_ltst").optical_depth_600nm.median().sort_index()
    x, y = observed.index.to_numpy(float), observed.to_numpy(float)
    target = np.asarray(target_sols, dtype=float)
    if len(x) < 2 or not np.all(np.isfinite(target)):
        raise ValueError("need two opacity observations and finite target sols")
    upper = np.searchsorted(x, target, side="left").clip(1, len(x) - 1)
    lower = upper - 1
    gap = x[upper] - x[lower]
    exact = np.isin(target, x)
    valid = ((target >= x[0]) & (target <= x[-1]) & (gap <= max_gap_sols)) | exact
    tau = np.where(valid, np.interp(target, x, y), np.nan)
    return tau, np.where(exact, 0.0, gap)


def metrics(predicted: np.ndarray, observed: np.ndarray) -> dict:
    error = predicted - observed
    return {
        "n": len(observed),
        "mae_wh": float(np.abs(error).mean()),
        "rmse_wh": float(np.sqrt(np.mean(error**2))),
        "bias_wh": float(error.mean()),
        "nrmse_pct_of_mean": float(100 * np.sqrt(np.mean(error**2)) / observed.mean()),
    }


def compare(data: Path = DATA) -> tuple[pd.DataFrame, dict]:
    """Fit one scale through sol 39; hold out all eligible sols 40..200.

    The 0.28%/sol dust rate is fixed from Lorenz et al. 2020, not optimized
    on this table. Thus this reproduces a literature-informed model on its
    originating mission and is not independent validation of that dust rate.
    """
    manifest = verify_sources(data)
    energy = mars.parse_insight_energy((data / "insight-energy.csv").read_bytes())
    opacity = mars.parse_insight_opacity((data / "nsyt_tau.csv").read_bytes())
    sols = energy.sol.to_numpy(float)
    tau, gap = align_opacity(sols + 0.5, opacity)
    # Derive the representative UTC date from the native current-file header,
    # whose first sample is at the stated LMST. Use measured sol 4, not a guessed
    # landing-midnight epoch. Seasonal changes within a sol are frozen.
    sample = mars.parse_insight_currents((data / "Solar_00004-00004.txt").read_bytes()).iloc[0]
    h, m, s = map(float, sample.lmst.split(":"))
    sol4_noon = sample.timestamp + pd.Timedelta(
        seconds=(12 - h - m / 60 - s / 3600) / 24 * mars.MARS_SOL_SECONDS
    )
    jd4_tt = sol4_noon.to_julian_date() + 69.184 / 86400  # historical TT-UTC, 2018-2019
    dates_tt = jd4_tt + (sols - 4) * mars.MARS_SOL_SECONDS / 86400
    bases = np.full((len(sols), 3), np.nan)
    for i in np.flatnonzero(np.isfinite(tau)):
        profile = mars.simulate_mars_sol(
            julian_date_tt=float(dates_tt[i]),
            latitude_deg=4.502,
            reference=PvwattsReference(1.0, 0.0),
            optical_depth=float(tau[i]),
            cell_temperature_c=25.0,
        )
        clean = profile.attrs["energy_wh"]
        bases[i, 0] = clean * mars.dust_retention(sols[i], loss_per_sol=0.0028)
        bases[i, 1] = clean
        # The Lorenz factor is constant over this frozen-season sol.
        bases[i, 2] = clean * (1 + 0.3 * tau[i])
    observed = energy.estimated_array_energy_wh.to_numpy(float)
    valid = np.isfinite(bases).all(axis=1)
    train, holdout = valid & (sols < 40), valid & (sols >= 40)
    result = energy.copy()
    result["tau_600nm_interpolated"] = tau
    result["opacity_bracket_gap_sols"] = gap
    result["array_dust_factor_scenario"] = mars.dust_retention(sols, loss_per_sol=0.0028)
    result["julian_date_tt_representative"] = dates_tt
    result["split"] = np.where(
        train, "calibration", np.where(holdout, "holdout", "no_opacity_support")
    )
    summary = {
        "source_dataset": manifest["dataset"],
        "samples_total": len(result),
        "samples_without_opacity_support": int((~valid).sum()),
        "calibration_last_sol": 39,
        "holdout_first_sol": 40,
        "opacity_max_interpolation_gap_sols": 15,
        "dust_loss_per_sol": 0.0028,
        "models": {},
        "interpretation": "Retrospective comparison with operational energy estimates. Only scale is fitted to early sols; literature dust rate originates from the same mission, so this is not independent mission validation. Interpolated 600-nm camera opacity is a proxy. Temperature/spectral/EPS behavior is absorbed in the scale, not identified physically.",
        "opacity_status": opacity.attrs["archive_status"],
    }
    for i, name in enumerate(
        ["geometry_atmosphere_panel_dust", "geometry_atmosphere", "geometry_only"]
    ):
        b = bases[:, i]
        scale = float(np.dot(b[train], observed[train]) / np.dot(b[train], b[train]))
        predicted = scale * b
        result[f"{name}_wh"] = predicted
        summary["models"][name] = {
            "fitted_reference_scale_w": scale,
            "calibration": metrics(predicted[train], observed[train]),
            "holdout": metrics(predicted[holdout], observed[holdout]),
        }
    return result, summary


def run(output: Path) -> dict:
    result, summary = compare()
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / "insight_comparison.csv", index=False, float_format="%.8f")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/mars_surface_pv"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
