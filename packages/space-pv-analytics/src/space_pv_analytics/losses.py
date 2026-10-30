"""Reconciled, evidence-labelled power losses and gap-aware energy accounting."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import pandas as pd

LOSS_CATEGORIES = MappingProxyType(
    {
        "solar_resource": "Solar resource",
        "geometry": "Eclipse and pointing",
        "optical": "Optical and spectral",
        "temperature": "Cell temperature",
        "degradation": "Radiation and aging",
        "electrical": "Mismatch and wiring",
        "conversion": "Power conversion",
        "operations": "Clipping, availability and curtailment",
        "unexplained": "Unexplained residual",
    }
)
"""Physical and operational reporting buckets; individual stages retain their names."""

_POWER_COLUMNS = {
    "timestamp",
    "expected_power_w",
    "modeled_power_w",
    "actual_power_w",
    "total_loss_w",
    "attributed_loss_w",
    "unexplained_loss_w",
    "valid",
}
_SUMMARY_COLUMNS = {
    "expected_energy_wh",
    "modeled_energy_wh",
    "actual_energy_wh",
    "gap_energy_wh",
    "attributed_energy_wh",
    "unexplained_energy_wh",
    "positive_gap_energy_wh",
    "surplus_energy_wh",
    "observed_duration_h",
    "window_duration_h",
    "coverage_fraction",
    "valid_samples",
    "total_samples",
    "valid_intervals",
    "total_intervals",
    "component",
    "category",
    "evidence",
    "net_loss_wh",
    "loss_wh",
    "gain_wh",
    "percent_expected",
}


@dataclass(frozen=True, slots=True)
class LossStage:
    """One ordered, cumulative power prediction with a declared evidence basis.

    ``power_column`` contains the prediction *after* this stage, not an
    independent loss estimate. Its contribution is the preceding prediction
    minus this prediction. ``evidence`` should identify the measurement, model,
    operating flag or explicit scenario assumption supporting the attribution.
    This label records the caller's evidence; it does not verify causality.

    ``category`` must be a key in :data:`LOSS_CATEGORIES`, except ``unexplained``
    which is reserved for the final model-minus-actual residual. Names must be
    unique snake_case identifiers within a breakdown.
    """

    name: str
    power_column: str
    category: str
    evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", self.name):
            raise ValueError("Stage name must be a snake_case identifier")
        if self.name == "unexplained":
            raise ValueError("The stage name 'unexplained' is reserved for the residual")
        if not isinstance(self.power_column, str) or not self.power_column.strip():
            raise ValueError("Stage power_column must be a nonempty column name")
        if self.category not in LOSS_CATEGORIES or self.category == "unexplained":
            raise ValueError(f"Unknown or reserved loss category: {self.category!r}")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("Every attributed stage requires a nonempty evidence description")


@dataclass(frozen=True, slots=True)
class PowerLossBreakdown:
    """Power ledger returned by :func:`power_loss_breakdown`.

    ``samples`` contains sorted timestamps, group identifiers, power predictions,
    signed total/attributed/unexplained losses and a common ``valid`` mask.
    ``components_w`` contains a column per stage plus ``unexplained``.
    ``categories_w`` combines stage contributions into reporting buckets.
    The three frames share the same positional index. Positive values are
    losses; negative values are gains. Treat these frames as read-only inputs
    to :func:`summarize_power_losses`.
    """

    samples: pd.DataFrame
    components_w: pd.DataFrame
    categories_w: pd.DataFrame
    stages: tuple[LossStage, ...]
    group_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PowerLossSummary:
    """Observed-interval energy totals, components and categories, all in Wh.

    ``totals`` reports the signed energy gap and common observation coverage
    per input group. ``components`` and ``categories`` report signed
    ``net_loss_wh``, nonnegative ``loss_wh`` / ``gain_wh`` and the signed
    percentage of expected energy. Percentages are NaN when expected energy
    is zero. All energy values are NaN when there are no usable intervals.

    Net contributions reconcile with the total gap. Gross positive/negative
    contributions can cancel between components, so their separate sums need
    not equal the total positive gap or total surplus.
    """

    totals: pd.DataFrame
    components: pd.DataFrame
    categories: pd.DataFrame


def power_loss_breakdown(
    frame: pd.DataFrame,
    stages: Sequence[LossStage] = (),
    *,
    expected_power_column: str = "expected_power_w",
    actual_power_column: str = "actual_power_w",
    timestamp_column: str = "timestamp",
    group_columns: Sequence[str] = (),
) -> PowerLossBreakdown:
    """Explain expected-minus-actual power using ordered cumulative predictions.

    For stages ``P1, ..., Pn`` and a declared expected baseline ``P0``, the
    signed contributions are ``P0-P1, P1-P2, ..., P(n-1)-Pn``. The unexplained
    remainder is ``Pn-actual``. Thus all contributions sum to
    ``expected-actual`` at every valid sample, including gains.

    Use an ideal reference baseline for a design loss budget, or a healthy
    operating model for underperformance analysis. Effects already included
    in the expected baseline must not be subtracted again. Attribution is
    order-dependent and conditional on the supplied evidence; this function
    does not diagnose causes from the residual or normalize supplied losses.

    Inputs must be already time-aligned in one DataFrame. Timestamps are
    converted to UTC (naive timestamps are assumed UTC), then sorted within
    each group. Duplicate group/timestamp pairs, missing identifiers, infinite
    powers and negative expected/stage predictions are rejected. Signed actual
    power is retained, including small negative telemetry sensor offsets.
    NaN in any required power excludes the entire row from the loss ledger;
    expected, final-modeled and actual powers remain in ``samples`` for
    inspection. Rows are not dropped, so energy accounting cannot interpolate
    across missing values.

    Parameters
    ----------
    frame : pandas.DataFrame
        Timestamps, expected/actual powers and optional cumulative stage powers.
    stages : sequence of LossStage
        Ordered stages from the chosen baseline to the final modeled power.
        With no stages, the whole gap remains unexplained.
    expected_power_column, actual_power_column : str
        Input power column names, in W, at the same declared electrical boundary.
    timestamp_column : str
        Input timestamp column. Do not combine unrelated campaign-relative times.
    group_columns : sequence of str
        Independent series identifiers, e.g. ``("panel_id",)``. Energy is never
        integrated across groups.
    """
    if frame.empty:
        raise ValueError("Power loss analysis requires at least one sample")
    if not frame.columns.is_unique:
        raise ValueError("Input column names must be unique")
    if isinstance(group_columns, str):
        raise ValueError("group_columns must be a sequence of column names, not a string")
    groups = tuple(group_columns)
    if len(set(groups)) != len(groups):
        raise ValueError("group_columns must be unique")
    if any(not isinstance(name, str) or not name for name in groups):
        raise ValueError("group_columns must contain nonempty column names")
    if set(groups) & (_POWER_COLUMNS | _SUMMARY_COLUMNS):
        raise ValueError("Group identifiers conflict with reserved result column names")
    stages = tuple(stages)
    if any(not isinstance(stage, LossStage) for stage in stages):
        raise TypeError("stages must contain LossStage objects")
    if len({stage.name for stage in stages}) != len(stages):
        raise ValueError("Stage names must be unique")
    power_columns = list(
        dict.fromkeys(
            [expected_power_column, actual_power_column, *(s.power_column for s in stages)]
        )
    )
    if timestamp_column in groups or timestamp_column in power_columns:
        raise ValueError("The timestamp column must be distinct from identifiers and powers")
    if set(groups) & set(power_columns):
        raise ValueError("Group identifiers cannot also be power columns")
    required = {timestamp_column, *groups, *power_columns}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    work = frame.loc[:, list(dict.fromkeys([*groups, timestamp_column, *power_columns]))].copy()
    work[timestamp_column] = pd.to_datetime(work[timestamp_column], utc=True, errors="raise")
    if work[timestamp_column].isna().any() or (groups and work[list(groups)].isna().any().any()):
        raise ValueError("Timestamps and group identifiers cannot be missing")
    if work.duplicated([*groups, timestamp_column]).any():
        raise ValueError("Duplicate timestamps within a group; align or aggregate them explicitly")
    work = work.sort_values([*groups, timestamp_column], kind="stable").reset_index(drop=True)
    powers: dict[str, np.ndarray] = {}
    for column in power_columns:
        numeric = pd.to_numeric(work[column], errors="raise")
        if np.iscomplexobj(numeric.to_numpy()):
            raise ValueError(f"Power column {column!r} must contain real values")
        values = numeric.to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(values).any():
            raise ValueError(f"Power column {column!r} contains an infinite value")
        powers[column] = values
    for column in {expected_power_column, *(s.power_column for s in stages)}:
        if (powers[column] < 0.0).any():
            raise ValueError(f"Expected/stage power column {column!r} must be nonnegative")
    valid = np.isfinite(np.column_stack(list(powers.values()))).all(axis=1)
    expected = powers[expected_power_column]
    actual = powers[actual_power_column]

    contributions: dict[str, np.ndarray] = {}
    previous = expected
    for stage in stages:
        after = powers[stage.power_column]
        contributions[stage.name] = np.where(valid, previous - after, np.nan)
        previous = after
    contributions["unexplained"] = np.where(valid, previous - actual, np.nan)
    components = pd.DataFrame(contributions)
    categories: dict[str, np.ndarray] = {}
    for category in LOSS_CATEGORIES:
        names = [s.name for s in stages if s.category == category]
        if category == "unexplained":
            names = ["unexplained"]
        if names:
            categories[category] = components[names].to_numpy().sum(axis=1)

    samples = work.loc[:, [*groups, timestamp_column]].rename(
        columns={timestamp_column: "timestamp"}
    )
    samples["expected_power_w"] = expected
    samples["modeled_power_w"] = previous
    samples["actual_power_w"] = actual
    samples["total_loss_w"] = np.where(valid, expected - actual, np.nan)
    samples["attributed_loss_w"] = np.where(valid, expected - previous, np.nan)
    samples["unexplained_loss_w"] = contributions["unexplained"]
    samples["valid"] = valid
    return PowerLossBreakdown(samples, components, pd.DataFrame(categories), stages, groups)


def _signed_energies(
    values: np.ndarray, hours: np.ndarray, intervals: np.ndarray
) -> tuple[float, float, float]:
    """Integrate linear segments, splitting losses/gains exactly at zero crossings."""
    if not intervals.any():
        return float("nan"), float("nan"), float("nan")
    left = values[:-1][intervals]
    right = values[1:][intervals]
    duration = hours[intervals]
    net = float(np.sum((0.5 * left + 0.5 * right) * duration))

    def positive_energy(a: np.ndarray, b: np.ndarray) -> float:
        mean = 0.5 * np.maximum(a, 0.0) + 0.5 * np.maximum(b, 0.0)
        down = (a > 0.0) & (b < 0.0)
        up = (a < 0.0) & (b > 0.0)
        mean[down] = 0.5 * a[down] * (a[down] / (a[down] - b[down]))
        mean[up] = 0.5 * b[up] * (b[up] / (b[up] - a[up]))
        return float(np.sum(mean * duration))

    return net, positive_energy(left, right), positive_energy(-left, -right)


def summarize_power_losses(
    breakdown: PowerLossBreakdown,
    *,
    max_gap_s: float,
) -> PowerLossSummary:
    """Integrate a power ledger on common, observed intervals only.

    ``max_gap_s`` is a required positive, finite maximum interval length in
    seconds. An interval contributes only when both endpoint rows are valid
    for *all* required powers and their separation is at most this threshold.
    Missing rows remain boundaries; no missing energy is filled or
    extrapolated. Each group uses its own recorded first-to-last time span
    for coverage. Coverage does not include any unrecorded time before or
    after that span.

    Power is assumed to vary linearly between accepted endpoints, giving
    trapezoidal energy integrals. Positive losses and gains split this line
    exactly where it crosses zero. Event discontinuities and packet timing
    uncertainty still require suitable sampling; the cutoff is not a claim
    that the intervening power is known. Choose it from the measurement
    cadence and context rather than applying a universal default.

    All stages, categories and total powers use the same interval mask, so
    net loss energy reconciles exactly (up to floating-point rounding).
    Percentages use expected energy over these same intervals; they are
    signed and are not normalized to make the loss buckets sum to 100%.
    """
    if not np.isscalar(max_gap_s) or not np.isfinite(max_gap_s) or max_gap_s <= 0:
        raise ValueError("max_gap_s must be a positive finite number of seconds")
    samples = breakdown.samples
    if samples.empty:
        raise ValueError("Power loss analysis requires at least one sample")
    if not samples.index.equals(breakdown.components_w.index) or not samples.index.equals(
        breakdown.categories_w.index
    ):
        raise ValueError("Breakdown frames no longer have matching sample indexes")
    groups = breakdown.group_columns
    if groups:
        grouped = samples.groupby(list(groups), sort=False, observed=True)
    else:
        grouped = [((), samples)]
    metadata = {s.name: (s.category, s.evidence) for s in breakdown.stages}
    metadata["unexplained"] = (
        "unexplained",
        "Final modeled power minus actual power; cause not identified",
    )
    totals: list[dict] = []
    component_rows: list[dict] = []
    category_rows: list[dict] = []
    for key, group in grouped:
        keys = key if isinstance(key, tuple) else (key,)
        identity = dict(zip(groups, keys, strict=True))
        times = group["timestamp"]
        seconds = times.diff().dt.total_seconds().to_numpy()[1:]
        if (seconds <= 0.0).any():
            raise ValueError("Breakdown samples must remain time-sorted and unique within groups")
        valid = group["valid"].to_numpy(dtype=bool)
        intervals = valid[:-1] & valid[1:] & (seconds <= max_gap_s)
        hours = seconds / 3600.0
        observed_h = float(np.sum(hours[intervals]))
        window_h = float((times.iloc[-1] - times.iloc[0]).total_seconds() / 3600.0)

        energies = {
            column: _signed_energies(group[column].to_numpy(dtype=float), hours, intervals)
            for column in (
                "expected_power_w",
                "modeled_power_w",
                "actual_power_w",
                "total_loss_w",
                "attributed_loss_w",
                "unexplained_loss_w",
            )
        }
        expected_wh = energies["expected_power_w"][0]
        gap_wh, positive_wh, surplus_wh = energies["total_loss_w"]
        totals.append(
            {
                **identity,
                "expected_energy_wh": expected_wh,
                "modeled_energy_wh": energies["modeled_power_w"][0],
                "actual_energy_wh": energies["actual_power_w"][0],
                "gap_energy_wh": gap_wh,
                "attributed_energy_wh": energies["attributed_loss_w"][0],
                "unexplained_energy_wh": energies["unexplained_loss_w"][0],
                "positive_gap_energy_wh": positive_wh,
                "surplus_energy_wh": surplus_wh,
                "observed_duration_h": observed_h,
                "window_duration_h": window_h,
                "coverage_fraction": observed_h / window_h if window_h > 0.0 else float("nan"),
                "valid_samples": int(valid.sum()),
                "total_samples": len(group),
                "valid_intervals": int(intervals.sum()),
                "total_intervals": len(intervals),
            }
        )
        for source, target, label in (
            (breakdown.components_w, component_rows, "component"),
            (breakdown.categories_w, category_rows, "category"),
        ):
            values = source.loc[group.index]
            for name in values.columns:
                net, loss, gain = _signed_energies(
                    values[name].to_numpy(dtype=float), hours, intervals
                )
                row = {
                    **identity,
                    label: name,
                    "net_loss_wh": net,
                    "loss_wh": loss,
                    "gain_wh": gain,
                    "percent_expected": 100.0 * net / expected_wh
                    if expected_wh > 0.0
                    else float("nan"),
                }
                if label == "component":
                    row["category"], row["evidence"] = metadata[name]
                target.append(row)
    return PowerLossSummary(
        pd.DataFrame(totals), pd.DataFrame(component_rows), pd.DataFrame(category_rows)
    )
