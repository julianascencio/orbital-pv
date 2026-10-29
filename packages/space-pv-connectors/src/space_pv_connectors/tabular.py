from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


def _slug(value: object) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def load_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported input format: {suffix}")


def normalize_birds_like(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df.columns = [_slug(c) for c in df.columns]
    timestamp_candidates = [
        c
        for c in df.columns
        if c in {"timestamp", "datetime", "date_time", "time"} or "timestamp" in c
    ]
    if not timestamp_candidates:
        dates = [c for c in df.columns if c == "date" or c.endswith("_date")]
        times = [c for c in df.columns if c == "time" or c.endswith("_time")]
        if dates and times:
            df["timestamp"] = pd.to_datetime(
                df[dates[0]].astype(str) + " " + df[times[0]].astype(str), errors="coerce", utc=True
            )
        else:
            raise ValueError(f"Could not discover timestamp column. Columns: {list(df.columns)}")
    else:
        df["timestamp"] = pd.to_datetime(df[timestamp_candidates[0]], errors="coerce", utc=True)

    voltage_cols = [c for c in df.columns if "volt" in c and "battery" not in c and "bat" not in c]
    current_cols = [
        c
        for c in df.columns
        if ("curr" in c or "amp" in c) and "battery" not in c and "bat" not in c
    ]
    temp_cols = [c for c in df.columns if "temp" in c and "battery" not in c and "bat" not in c]
    if not voltage_cols or not current_cols:
        req = {"timestamp", "panel_id", "voltage_v", "current_a"}
        if req.issubset(df.columns):
            return df[list(req | ({"temperature_c"} & set(df.columns)))].dropna(
                subset=["timestamp"]
            )
        raise ValueError(
            f"Could not discover panel voltage/current columns. voltage={voltage_cols}, current={current_cols}"
        )

    def panel_key(c: str) -> str:
        c = re.sub(r"(?:voltage|volt|current|curr|amp|ma|mv|v|a|temperature|temp)", "", c)
        return re.sub(r"_+", "_", c).strip("_") or "panel"

    v_map = {panel_key(c): c for c in voltage_cols}
    i_map = {panel_key(c): c for c in current_cols}
    common = sorted(set(v_map) & set(i_map))
    if not common and len(voltage_cols) == len(current_cols):
        common = [f"panel_{i + 1}" for i in range(len(voltage_cols))]
        v_map = dict(zip(common, voltage_cols, strict=True))
        i_map = dict(zip(common, current_cols, strict=True))
    if not common:
        raise ValueError("Could not pair voltage and current columns into panels")
    temp_map = {panel_key(c): c for c in temp_cols}
    rows = []
    for panel in common:
        part = pd.DataFrame(
            {
                "timestamp": df["timestamp"],
                "panel_id": panel,
                "voltage_v": pd.to_numeric(df[v_map[panel]], errors="coerce"),
                "current_a": pd.to_numeric(df[i_map[panel]], errors="coerce"),
            }
        )
        if part["voltage_v"].abs().median() > 100:
            part["voltage_v"] /= 1000.0
        if part["current_a"].abs().median() > 10:
            part["current_a"] /= 1000.0
        if panel in temp_map:
            part["temperature_c"] = pd.to_numeric(df[temp_map[panel]], errors="coerce")
        rows.append(part)
    return pd.concat(rows, ignore_index=True).dropna(subset=["timestamp", "voltage_v", "current_a"])


def make_demo_telemetry(
    *, seed: int = 42, days: int = 45, samples_per_day: int = 80
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = days * samples_per_day
    t = pd.date_range("2026-01-01", periods=n, freq=f"{24 * 60 / samples_per_day:.2f}min", tz="UTC")
    age_days = np.arange(n) / samples_per_day
    orbit_phase = np.arange(n) % samples_per_day
    illumination = np.clip(np.sin(2 * np.pi * orbit_phase / samples_per_day), 0, None)
    degradation = 1.0 - 0.00008 * age_days
    temperature = 5 + 28 * illumination + rng.normal(0, 1.5, n)
    voltage = (2.55 - 0.0025 * (temperature - 20)) * degradation + rng.normal(0, 0.015, n)
    current = 0.42 * illumination * degradation + rng.normal(0, 0.006, n)
    current = np.clip(current, 0, None)
    current[int(n * 0.72) :] *= 0.78
    idx = rng.choice(n, size=max(5, n // 250), replace=False)
    current[idx] *= rng.uniform(0.05, 0.45, len(idx))
    return pd.DataFrame(
        {
            "timestamp": t,
            "panel_id": "panel_x",
            "voltage_v": voltage,
            "current_a": current,
            "temperature_c": temperature,
        }
    )
