"""Transparent irradiance baselines for calibrated cloud/clear-sky-index grids.

These are operationally useful comparison methods, not reproductions of a
foundation weather model. Input irradiance or cloud transmission must already
be physically retrieved; raw ABI/SEVIRI radiance is not irradiance. Forecasts
record retrieval provenance, motion assumptions and missing inflow boundaries.
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


def _ndimage() -> Any:
    try:
        return importlib.import_module("scipy.ndimage")
    except ImportError as exc:
        raise ImportError("Cloud motion requires orbital-pv[ground]") from exc


def _field(values: Any, *, name: str, ndim: int | None = None) -> np.ndarray:
    array = np.ma.asarray(values, dtype=float)
    result = np.asarray(array.filled(np.nan), dtype=float)
    if not result.size or (ndim is not None and result.ndim != ndim):
        raise ValueError(f"{name} must be a nonempty {ndim or 'numeric'} dimensional array")
    if np.isinf(result).any():
        raise ValueError(f"{name} cannot contain infinite values")
    return result


def clear_sky_persistence(
    observed_ghi: Any,
    latest_clear_sky_ghi: Any,
    future_clear_sky_ghi: Any,
    *,
    minimum_clear_sky_wm2: float = 20.0,
    maximum_clear_sky_index: float = 1.5,
) -> np.ma.MaskedArray:
    """Persist the latest daytime clear-sky index into future clear-sky GHI.

    Inputs broadcast, e.g. a spatial grid and ``(lead, row, column)`` future
    values. Future night (clear-sky GHI == 0) is zero. A nighttime/latest
    low-sun observation does not define a future daytime index and is masked.
    The maximum index allows specified cloud enhancement and is explicit.
    Values are W/m², not accumulated radiation energy.
    """
    if not math.isfinite(minimum_clear_sky_wm2) or minimum_clear_sky_wm2 <= 0:
        raise ValueError("minimum_clear_sky_wm2 must be finite and positive")
    if not math.isfinite(maximum_clear_sky_index) or maximum_clear_sky_index <= 0:
        raise ValueError("maximum_clear_sky_index must be finite and positive")
    observed, latest, future = np.broadcast_arrays(
        _field(observed_ghi, name="observed_ghi"),
        _field(latest_clear_sky_ghi, name="latest_clear_sky_ghi"),
        _field(future_clear_sky_ghi, name="future_clear_sky_ghi"),
    )
    if np.any(observed < 0) or np.any(latest < 0) or np.any(future < 0):
        raise ValueError("GHI must be nonnegative; filter invalid retrievals explicitly")
    index = np.full(observed.shape, np.nan)
    usable = np.isfinite(observed) & np.isfinite(latest) & (latest >= minimum_clear_sky_wm2)
    np.divide(observed, latest, out=index, where=usable)
    forecast = np.clip(index, 0, maximum_clear_sky_index) * future
    forecast = np.where(future == 0, 0.0, forecast)
    return np.ma.masked_invalid(forecast)


@dataclass(frozen=True, slots=True)
class CloudMotion:
    """Global or dense apparent motion in pixels/minute on the supplied grid."""

    row_pixels_per_minute: Any
    column_pixels_per_minute: Any
    minutes_between: float
    method: str
    quality: dict[str, Any]


def estimate_cloud_motion(
    previous: Any,
    current: Any,
    *,
    minutes_between: float,
    method: str = "lucas_kanade",
    max_shift_pixels: int = 30,
    local_window: int = 9,
    iterations: int = 3,
) -> CloudMotion:
    """Estimate translation, optionally refined by local Lucas-Kanade optical flow.

    Phase correlation estimates integer global advection. The default then
    solves local gradient least squares after warping, with Gaussian spatial
    averaging and at most two pixels correction per iteration. Texture-poor
    pixels retain the global estimate. This transparent classical baseline
    assumes brightness conservation; cloud growth and parallax violate it.
    A rectangular projected grid and unchanged retrieval scale are required.
    """
    if not math.isfinite(minutes_between) or minutes_between <= 0:
        raise ValueError("minutes_between must be finite and positive")
    if method not in {"phase_correlation", "lucas_kanade"}:
        raise ValueError("method must be phase_correlation or lucas_kanade")
    if (
        isinstance(max_shift_pixels, bool)
        or not isinstance(max_shift_pixels, int)
        or max_shift_pixels < 1
    ):
        raise ValueError("max_shift_pixels must be a positive integer")
    if (
        isinstance(local_window, bool)
        or not isinstance(local_window, int)
        or local_window < 3
        or local_window % 2 != 1
    ):
        raise ValueError("local_window must be an odd integer >= 3")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or not 1 <= iterations <= 20:
        raise ValueError("iterations must be an integer from 1 to 20")
    old, new = _field(previous, name="previous", ndim=2), _field(current, name="current", ndim=2)
    if old.shape != new.shape or min(old.shape) < 8:
        raise ValueError(
            "Cloud grids must align and each dimension must have at least eight pixels"
        )
    common = np.isfinite(old) & np.isfinite(new)
    if common.mean() < 0.5 or min(float(np.nanstd(old)), float(np.nanstd(new))) <= 1e-8:
        raise ValueError("Motion estimation needs at least half valid overlap and spatial texture")
    # Invalid pixels are mean-filled only for the global spectral estimate;
    # output advection retains missing observations rather than fabricating data.
    old_zero = np.where(np.isfinite(old), old - np.nanmean(old), 0)
    new_zero = np.where(np.isfinite(new), new - np.nanmean(new), 0)
    cross = np.fft.fft2(new_zero) * np.conj(np.fft.fft2(old_zero))
    absolute = np.abs(cross)
    normalized = np.divide(cross, absolute, out=np.zeros_like(cross), where=absolute > 1e-12)
    correlation = np.fft.ifft2(normalized).real
    row_shifts = np.fft.fftfreq(old.shape[0]) * old.shape[0]
    col_shifts = np.fft.fftfreq(old.shape[1]) * old.shape[1]
    allowed = (np.abs(row_shifts[:, None]) <= max_shift_pixels) & (
        np.abs(col_shifts[None, :]) <= max_shift_pixels
    )
    peak = np.unravel_index(np.argmax(np.where(allowed, correlation, -np.inf)), old.shape)
    dy, dx = float(round(row_shifts[peak[0]])), float(round(col_shifts[peak[1]]))
    quality: dict[str, Any] = {
        "valid_overlap_fraction": float(common.mean()),
        "global_row_shift_pixels": dy,
        "global_column_shift_pixels": dx,
        "phase_peak": float(correlation[peak]),
        "phase_peak_to_rms": float(
            correlation[peak] / max(float(np.sqrt(np.mean(correlation[allowed] ** 2))), 1e-12)
        ),
        "global_shift_hits_search_limit": bool(
            abs(dy) == max_shift_pixels or abs(dx) == max_shift_pixels
        ),
        "grid_units": "pixels; caller must retain projection and native pixel size",
    }
    if method == "phase_correlation":
        return CloudMotion(
            dy / minutes_between, dx / minutes_between, minutes_between, method, quality
        )
    ndimage = _ndimage()
    rows, cols = np.indices(old.shape, dtype=float)
    uy, ux = np.full(old.shape, dy), np.full(old.shape, dx)
    sigma = local_window / 6.0
    old_filled = np.where(np.isfinite(old), old, np.nanmean(old))
    gy, gx = np.gradient(ndimage.gaussian_filter(old_filled, 0.8))
    refined = np.zeros(old.shape, dtype=bool)
    for _ in range(iterations):
        coordinates = np.array([rows - uy, cols - ux])
        warped = ndimage.map_coordinates(old_filled, coordinates, order=1, mode="nearest")
        ix = ndimage.map_coordinates(gx, coordinates, order=1, mode="nearest")
        iy = ndimage.map_coordinates(gy, coordinates, order=1, mode="nearest")
        known = (
            ndimage.map_coordinates(
                np.isfinite(old).astype(float), coordinates, order=1, mode="constant", cval=0
            )
            > 0.999
        )
        valid = known & np.isfinite(new)
        residual = np.where(valid, warped - new, 0)
        xx = ndimage.gaussian_filter(np.where(valid, ix * ix, 0), sigma)
        yy = ndimage.gaussian_filter(np.where(valid, iy * iy, 0), sigma)
        xy = ndimage.gaussian_filter(np.where(valid, ix * iy, 0), sigma)
        bx = ndimage.gaussian_filter(ix * residual, sigma)
        by = ndimage.gaussian_filter(iy * residual, sigma)
        determinant = xx * yy - xy**2
        trace = xx + yy
        supported = valid & (determinant > np.maximum(1e-14, 1e-3 * trace**2))
        correction_x = np.divide(
            yy * bx - xy * by, determinant, out=np.zeros_like(xx), where=supported
        )
        correction_y = np.divide(
            xx * by - xy * bx, determinant, out=np.zeros_like(xx), where=supported
        )
        ux += np.clip(correction_x, -2, 2)
        uy += np.clip(correction_y, -2, 2)
        ux = np.clip(ux, -max_shift_pixels, max_shift_pixels)
        uy = np.clip(uy, -max_shift_pixels, max_shift_pixels)
        refined |= supported
    quality.update(
        local_window=local_window,
        iterations=iterations,
        locally_refined_fraction=float(refined.mean()),
        sparse_texture_fallback="global phase-correlation motion",
    )
    return CloudMotion(uy / minutes_between, ux / minutes_between, minutes_between, method, quality)


def advect_cloud_field(
    field: Any, motion: CloudMotion, *, lead_minutes: float
) -> np.ma.MaskedArray:
    """Backtrace a scalar field under frozen motion without wrapping image edges.

    Missing incoming boundaries and missing source pixels remain masked.
    Dense flow is treated as constant over the forecast horizon; no learned
    cloud creation/dissipation is implied. Zero lead returns the usable field.
    """
    if not math.isfinite(lead_minutes) or lead_minutes < 0:
        raise ValueError("lead_minutes must be finite and nonnegative")
    source = _field(field, name="field", ndim=2)
    vy, vx = np.broadcast_arrays(
        np.asarray(motion.row_pixels_per_minute, dtype=float),
        np.asarray(motion.column_pixels_per_minute, dtype=float),
    )
    if vy.shape not in {(), source.shape} or not np.isfinite(vy).all() or not np.isfinite(vx).all():
        raise ValueError("Motion must be finite scalar velocities or fields matching the grid")
    rows, cols = np.indices(source.shape, dtype=float)
    coordinates = np.array([rows - vy * lead_minutes, cols - vx * lead_minutes])
    ndimage = _ndimage()
    known = ndimage.map_coordinates(
        np.isfinite(source).astype(float), coordinates, order=1, mode="constant", cval=0
    )
    result = ndimage.map_coordinates(
        np.nan_to_num(source, nan=0), coordinates, order=1, mode="constant", cval=0
    )
    return np.ma.array(result, mask=known < 1 - 1e-9)


@dataclass(frozen=True, slots=True)
class IrradianceForecast:
    """GHI forecast (lead, rows, columns), motion and auditable assumptions."""

    ghi_wm2: np.ma.MaskedArray
    lead_minutes: tuple[float, ...]
    motion: CloudMotion
    metadata: dict[str, Any]


def forecast_irradiance(
    previous_clear_sky_index: Any,
    current_clear_sky_index: Any,
    future_clear_sky_ghi: Any,
    *,
    minutes_between: float,
    lead_minutes: Any,
    source: str,
    license_name: str,
    method: str = "lucas_kanade",
    max_shift_pixels: int = 30,
    maximum_clear_sky_index: float = 1.5,
) -> IrradianceForecast:
    """Advect retrieved clear-sky index and multiply by future clear-sky GHI.

    ``future_clear_sky_ghi`` is W/m², with shape (leads, rows, columns).
    Prior/current inputs are dimensionless retrieved GHI/clear-sky GHI on
    the same grid. Acquisition spacing, source and license are explicit.
    Raw satellite radiances and cloud mask class codes are not valid inputs.
    """
    if not source.strip() or not license_name.strip():
        raise ValueError("Record the retrieval source and license")
    if not math.isfinite(maximum_clear_sky_index) or maximum_clear_sky_index <= 0:
        raise ValueError("maximum_clear_sky_index must be finite and positive")
    leads = np.asarray(lead_minutes, dtype=float)
    if (
        leads.ndim != 1
        or not len(leads)
        or not np.isfinite(leads).all()
        or np.any(leads < 0)
        or np.any(np.diff(leads) <= 0)
    ):
        raise ValueError("lead_minutes must be finite, nonnegative and strictly increasing")
    current = _field(current_clear_sky_index, name="current_clear_sky_index", ndim=2)
    old = _field(previous_clear_sky_index, name="previous_clear_sky_index", ndim=2)
    future = _field(future_clear_sky_ghi, name="future_clear_sky_ghi", ndim=3)
    if future.shape != (len(leads), *current.shape):
        raise ValueError("Future clear-sky GHI must have shape (lead, rows, columns)")
    if np.any(old < 0) or np.any(current < 0) or np.any(future < 0):
        raise ValueError("Clear-sky indices and GHI cannot be negative")
    motion = estimate_cloud_motion(
        old,
        current,
        minutes_between=minutes_between,
        method=method,
        max_shift_pixels=max_shift_pixels,
    )
    predictions = []
    for lead, clear in zip(leads, future, strict=True):
        shifted = advect_cloud_field(current, motion, lead_minutes=float(lead))
        index = np.clip(shifted.filled(np.nan), 0, maximum_clear_sky_index)
        ghi = index * clear
        ghi[clear == 0] = 0
        predictions.append(np.ma.masked_invalid(ghi))
    return IrradianceForecast(
        np.ma.stack(predictions),
        tuple(float(value) for value in leads),
        motion,
        {
            "method": "frozen retrieved clear-sky-index advection",
            "motion_method": motion.method,
            "source": source,
            "license": license_name,
            "inferred": True,
            "maximum_clear_sky_index": maximum_clear_sky_index,
            "boundary_policy": "unknown incoming cloud field is masked",
            "native_resolution": "must be supplied with retrieval; interpolating adds no observations",
            "limitations": [
                "no cloud growth/dissipation",
                "no parallax correction",
                "retrieval and clear-sky-model uncertainty not calibrated",
                "not a Baguan-solar reproduction",
            ],
        },
    )


def blend_irradiance_forecasts(
    nowcast: Any,
    weather_forecast: Any,
    *,
    lead_minutes: Any,
    forecast_origin: str,
    weather_issue_time: str,
    weather_kind: str = "forecast",
    transition_minutes: float = 120,
) -> np.ma.MaskedArray:
    """Blend with exponential nowcast weight exp(-lead/transition_minutes).

    Use a weather forecast issued no later than the forecast origin. A
    reanalysis is rejected as operational forecast input to prevent hindsight
    leakage. Inputs are already on the same time/grid/unit support. Missing
    one source uses the other; neither source available remains masked.
    Transition time is a caller choice, not fitted on the evaluation period.
    """
    if weather_kind != "forecast":
        raise ValueError(
            "Operational fusion requires weather_kind='forecast'; reanalysis leaks hindsight"
        )
    origin, issued = pd.Timestamp(forecast_origin), pd.Timestamp(weather_issue_time)
    origin = origin.tz_localize("UTC") if origin.tz is None else origin.tz_convert("UTC")
    issued = issued.tz_localize("UTC") if issued.tz is None else issued.tz_convert("UTC")
    if pd.isna(origin) or pd.isna(issued) or issued > origin:
        raise ValueError("Weather forecast must be issued no later than the forecast origin")
    if not math.isfinite(transition_minutes) or transition_minutes <= 0:
        raise ValueError("transition_minutes must be finite and positive")
    short, long = _field(nowcast, name="nowcast"), _field(weather_forecast, name="weather_forecast")
    leads = np.asarray(lead_minutes, dtype=float)
    if (
        short.shape != long.shape
        or short.ndim < 1
        or leads.ndim != 1
        or short.shape[0] != len(leads)
    ):
        raise ValueError("Forecast grids must match and axis 0 must index lead_minutes")
    if (
        not np.isfinite(leads).all()
        or np.any(leads < 0)
        or np.any(np.diff(leads) <= 0)
        or np.any(short < 0)
        or np.any(long < 0)
    ):
        raise ValueError("Require increasing nonnegative leads and nonnegative irradiance")
    weight = np.exp(-leads / transition_minutes).reshape((len(leads),) + (1,) * (short.ndim - 1))
    combined = weight * short + (1 - weight) * long
    combined = np.where(~np.isfinite(short), long, combined)
    combined = np.where(~np.isfinite(long), short, combined)
    return np.ma.masked_invalid(combined)


def evaluate_irradiance_forecast(
    predicted: Any, observed: Any, *, persistence: Any | None = None
) -> dict[str, Any]:
    """MAE/RMSE/bias on shared valid support; optional RMSE skill vs persistence.

    Day/night and lead stratification should be applied by the caller before
    scoring. When a persistence reference is supplied, all metrics use the
    exact same three-way support to avoid favourable missing-pixel selection.
    """
    estimate, truth = _field(predicted, name="predicted"), _field(observed, name="observed")
    if estimate.shape != truth.shape:
        raise ValueError("Prediction and observation must have identical support")
    valid = np.isfinite(estimate) & np.isfinite(truth)
    baseline = None
    if persistence is not None:
        baseline = _field(persistence, name="persistence")
        if baseline.shape != truth.shape:
            raise ValueError("Persistence must match the same support")
        valid &= np.isfinite(baseline)
    if not valid.any():
        raise ValueError("No jointly usable forecast and observation samples")
    errors = estimate[valid] - truth[valid]
    rmse = float(np.sqrt(np.mean(errors**2)))
    result = {
        "n": int(valid.sum()),
        "support_fraction": float(valid.mean()),
        "mae_wm2": float(np.abs(errors).mean()),
        "rmse_wm2": rmse,
        "bias_wm2": float(errors.mean()),
    }
    if baseline is not None:
        base_rmse = float(np.sqrt(np.mean((baseline[valid] - truth[valid]) ** 2)))
        result.update(
            persistence_rmse_wm2=base_rmse,
            rmse_skill_vs_persistence=1 - rmse / base_rmse if base_rmse else None,
        )
    return result


__all__ = [
    "CloudMotion",
    "IrradianceForecast",
    "advect_cloud_field",
    "blend_irradiance_forecasts",
    "clear_sky_persistence",
    "estimate_cloud_motion",
    "evaluate_irradiance_forecast",
    "forecast_irradiance",
]
