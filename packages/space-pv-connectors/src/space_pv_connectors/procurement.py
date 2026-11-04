"""Load auditable array-trade inputs using the shared tabular connector."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .tabular import load_table

NUMERIC_COLUMNS = ("bol_w_m2", "eol_retention", "kg_m2", "cost_m2")
TEXT_COLUMNS = ("name", "evidence_status", "source_url", "assumptions")


def load_array_offers(path: str | Path) -> pd.DataFrame:
    """Load CSV/Excel/Parquet offers without converting efficiency or units.

    Required numeric columns are array-level BOL W/m², EOL retention, kg/m²,
    and procurement currency/m². Currency and EOL duration must be common and
    documented externally. Source links establish provenance, not validation.
    Evidence status is measured, imported, modeled, or synthetic; all nonempty
    text and extra metadata columns are preserved.
    """
    frame = load_table(path)
    missing = set(NUMERIC_COLUMNS + TEXT_COLUMNS) - set(frame.columns)
    if missing or frame.empty:
        raise ValueError(f"Empty offers or missing required columns: {sorted(missing)}")
    for column in TEXT_COLUMNS:
        if (
            not frame[column]
            .map(lambda value: isinstance(value, str) and bool(value.strip()))
            .all()
        ):
            raise ValueError(f"{column} must contain nonempty text")
    if frame.name.duplicated().any():
        raise ValueError("Offer names must be unique")
    if not frame.evidence_status.isin({"measured", "imported", "modeled", "synthetic"}).all():
        raise ValueError("Unknown evidence_status")
    for column in NUMERIC_COLUMNS:
        values = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f"{column} must be finite and nonnegative")
        if column != "cost_m2" and (values == 0).any():
            raise ValueError(f"{column} must be positive")
        frame[column] = values
    if (frame.eol_retention > 1).any():
        raise ValueError("eol_retention must not exceed 1")
    return frame
