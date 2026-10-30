from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

import pandas as pd

from .http_base import DownloadReceipt, HttpConnector
from .tabular import normalize_birds_like


class BirdsEPSConnector(HttpConnector):
    """Connector for the public BIRDS on-orbit EPS dataset."""

    API = "https://api.github.com/repos/BIRDSOpenSource/EPS_dataset/contents"
    SATELLITES: ClassVar[frozenset[str]] = frozenset({"NEPALISAT", "RAAVANA", "TSURU", "UGUISU"})
    DATASET_DOI = "10.17632/8kp25ycf63.1"

    def download(self, satellite: str, destination: str | Path) -> DownloadReceipt:
        """Download one satellite workbook from the upstream BIRDS repository."""

        name = satellite.upper()
        if name not in self.SATELLITES:
            raise ValueError(
                f"Unknown BIRDS EPS satellite: {satellite}; choose {sorted(self.SATELLITES)}"
            )
        metadata = self._client.get(f"{self.API}/{name}.xlsx")
        metadata.raise_for_status()
        download_url = metadata.json()["download_url"]
        response = self._client.get(download_url)
        response.raise_for_status()
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return self.receipt("BIRDS EPS", download_url, response.content, path=path)

    def download_frame(
        self,
        satellite: str,
        destination: str | Path,
        *,
        normalized: bool = True,
        campaign_year: int | None = None,
    ) -> pd.DataFrame:
        """Download and load a BIRDS EPS workbook.

        ``campaign_year`` supplies the year only for campaign sheet names that
        omit it; see :func:`load_birds_eps_workbook` for the time convention.
        """

        receipt = self.download(satellite, destination)
        path = Path(receipt.path or destination)
        return load_birds_eps_workbook(path, normalized=normalized, campaign_year=campaign_year)


_BIRDS_PANEL_CODES = {
    "py": "+Y",
    "px": "+X",
    "mz": "-Z",
    "mx": "-X",
    "pz": "+Z",
}

_BIRDS_TEST_SHEETS = frozenset({"test1 w batt", "test2 wo batt"})


def _column_slug(value: object) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _campaign_anchor(
    sheet_name: str | None,
    campaign_year: int | None,
) -> tuple[pd.Timestamp, str]:
    """Parse a dated campaign without guessing an omitted year or clock time."""

    name = " ".join((sheet_name or "").split())
    basis = "sheet_date"
    if not re.search(r"\b\d{4}\b", name):
        if not re.fullmatch(r"(?:[A-Za-z]+\s+\d{1,2}|\d{1,2}\s+[A-Za-z]+)", name):
            raise ValueError(
                f"BIRDS campaign sheet {sheet_name!r} has no recognizable date; "
                "numeric Time Stamp values are elapsed seconds, not Unix timestamps."
            )
        if campaign_year is None:
            raise ValueError(
                f"BIRDS campaign sheet {sheet_name!r} omits its year; "
                "pass campaign_year explicitly after checking the workbook date context."
            )
        name = f"{name} {campaign_year}"
        basis = "explicit_campaign_year"

    try:
        parsed = pd.to_datetime(name, utc=True, dayfirst=True)
        if not isinstance(parsed, pd.Timestamp):
            raise ValueError("Campaign date is missing")
        anchor = parsed.normalize()
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Cannot parse BIRDS campaign date from sheet {sheet_name!r}") from exc
    return anchor, basis


def _normalize_birds_calibrated(
    frame: pd.DataFrame,
    *,
    campaign_date: str | None = None,
    campaign_year: int | None = None,
) -> pd.DataFrame | None:
    columns = {_column_slug(column): column for column in frame.columns}
    if "time_stamp" not in columns:
        return None

    available = [
        code for code in _BIRDS_PANEL_CODES if f"v{code}_mv" in columns and f"i{code}_ma" in columns
    ]
    if not available:
        return None

    raw_timestamp = frame[columns["time_stamp"]]
    numeric_timestamp = pd.to_numeric(raw_timestamp, errors="coerce")
    numeric_clock = (
        not pd.api.types.is_datetime64_any_dtype(raw_timestamp) and numeric_timestamp.notna().any()
    )
    metadata: dict[str, object]
    if numeric_clock:
        campaign_start, date_basis = _campaign_anchor(campaign_date, campaign_year)
        # Some sheets contain hundreds of calibration/footer rows with no
        # clock. Their proportion must not turn elapsed seconds into epoch ns.
        numeric_timestamp = numeric_timestamp.where(
            numeric_timestamp.ge(0) & numeric_timestamp.lt(float("inf"))
        )
        timestamp = campaign_start + pd.to_timedelta(numeric_timestamp, unit="s")
        metadata = {
            "elapsed_seconds": numeric_timestamp,
            "campaign_date": campaign_start,
            "timestamp_basis": "campaign_date_midnight_plus_elapsed_seconds",
            "campaign_date_basis": date_basis,
        }
    else:
        timestamp = pd.to_datetime(raw_timestamp, errors="coerce", utc=True)
        metadata = {"timestamp_basis": "reported_timestamp"}
    parts: list[pd.DataFrame] = []
    for code in available:
        part = pd.DataFrame(
            {
                "timestamp": timestamp,
                "panel_id": _BIRDS_PANEL_CODES[code],
                "voltage_v": pd.to_numeric(frame[columns[f"v{code}_mv"]], errors="coerce") / 1000.0,
                "current_a": pd.to_numeric(frame[columns[f"i{code}_ma"]], errors="coerce") / 1000.0,
                **metadata,
            }
        )
        temp_key = f"t{code}_c"
        if temp_key in columns:
            part["temperature_c"] = pd.to_numeric(frame[columns[temp_key]], errors="coerce")
        parts.append(part)

    return pd.concat(parts, ignore_index=True).dropna(
        subset=["timestamp", "voltage_v", "current_a"]
    )


def _header_score(values: list[object]) -> int:
    text = " ".join(str(value).lower() for value in values if pd.notna(value))
    keywords = ("volt", "current", "curr", "temp", "date", "time", "panel", "solar", "battery")
    return sum(keyword in text for keyword in keywords)


def _discover_header_row(path: Path | pd.ExcelFile, sheet_name: str) -> int:
    preview = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=30)
    scores = [_header_score(row.tolist()) for _, row in preview.iterrows()]
    if not scores:
        return 0
    best = int(max(range(len(scores)), key=scores.__getitem__))
    return best if scores[best] >= 2 else 0


def load_birds_eps_workbook(
    path: str | Path,
    *,
    normalized: bool = True,
    campaign_year: int | None = None,
) -> pd.DataFrame:
    """Load a downloaded BIRDS EPS workbook into the canonical panel schema.

    Parameters
    ----------
    path : str or pathlib.Path
        Downloaded upstream XLSX workbook.
    normalized : bool, default True
        Return panel-level flight telemetry. The known undated TSURU sheets
        ``Test1 w batt`` and ``Test2 wo batt`` are excluded from this mode.
        ``False`` returns raw rows from every nonempty sheet, including tests.
    campaign_year : int, optional
        Explicit year for campaign sheet dates that omit it. For example, the
        TSURU 2021 flight campaigns require ``campaign_year=2021``. A year
        already stated in a sheet name is always preserved. No current-year
        assumption is made; an omitted year raises an actionable error.

    Notes
    -----
    Calibrated numeric ``Time Stamp`` values are elapsed seconds. The returned
    ``timestamp`` anchors these to midnight on ``campaign_date`` for ordering;
    this is **not a known absolute UTC acquisition time**. The original clock
    is retained in ``elapsed_seconds`` and the convention in ``timestamp_basis``.
    ``campaign_date_basis`` records whether a year was supplied by the caller.
    Rows without a valid elapsed clock or voltage/current pair are omitted.
    """

    if campaign_year is not None and (
        isinstance(campaign_year, bool)
        or not isinstance(campaign_year, int)
        or not 1 <= campaign_year <= 9999
    ):
        raise ValueError("campaign_year must be an integer year between 1 and 9999")

    workbook = Path(path)
    raw_parts: list[pd.DataFrame] = []
    normalized_parts: list[pd.DataFrame] = []
    errors: list[str] = []

    with pd.ExcelFile(workbook) as excel:
        for sheet in excel.sheet_names:
            if normalized and " ".join(sheet.lower().split()) in _BIRDS_TEST_SHEETS:
                continue
            header_row = _discover_header_row(excel, sheet)
            frame = pd.read_excel(excel, sheet_name=sheet, header=header_row)
            frame = frame.dropna(how="all")
            if frame.empty:
                continue
            frame["source_sheet"] = sheet
            raw_parts.append(frame)

            if normalized:
                clean = frame.drop(columns=["source_sheet"])
                part = _normalize_birds_calibrated(
                    clean, campaign_date=sheet, campaign_year=campaign_year
                )
                if part is None:
                    try:
                        part = normalize_birds_like(clean)
                    except ValueError as exc:
                        errors.append(f"{sheet}: {exc}")
                        continue
                if part.empty:
                    errors.append(f"{sheet}: no valid panel observations")
                    continue
                part["source_sheet"] = sheet
                normalized_parts.append(part)

    if normalized:
        if not normalized_parts:
            detail = "; ".join(errors) if errors else "no readable sheets"
            raise ValueError(f"Could not normalize BIRDS EPS workbook {workbook.name}: {detail}")
        return (
            pd.concat(normalized_parts, ignore_index=True)
            .sort_values(["panel_id", "timestamp"])
            .reset_index(drop=True)
        )

    if not raw_parts:
        raise ValueError(f"No readable sheets found in {workbook}")
    return pd.concat(raw_parts, ignore_index=True)


__all__ = ["BirdsEPSConnector", "load_birds_eps_workbook"]
