from __future__ import annotations

from pathlib import Path
import re
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
    ) -> pd.DataFrame:
        """Download and load a BIRDS EPS workbook."""

        receipt = self.download(satellite, destination)
        path = Path(receipt.path or destination)
        return load_birds_eps_workbook(path, normalized=normalized)


_BIRDS_PANEL_CODES = {
    "py": "+Y",
    "px": "+X",
    "mz": "-Z",
    "mx": "-X",
    "pz": "+Z",
}


def _column_slug(value: object) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _normalize_birds_calibrated(frame: pd.DataFrame) -> pd.DataFrame | None:
    columns = {_column_slug(column): column for column in frame.columns}
    if "time_stamp" not in columns:
        return None

    available = [
        code for code in _BIRDS_PANEL_CODES if f"v{code}_mv" in columns and f"i{code}_ma" in columns
    ]
    if not available:
        return None

    timestamp = pd.to_datetime(frame[columns["time_stamp"]], errors="coerce", utc=True)
    parts: list[pd.DataFrame] = []
    for code in available:
        part = pd.DataFrame(
            {
                "timestamp": timestamp,
                "panel_id": _BIRDS_PANEL_CODES[code],
                "voltage_v": pd.to_numeric(frame[columns[f"v{code}_mv"]], errors="coerce") / 1000.0,
                "current_a": pd.to_numeric(frame[columns[f"i{code}_ma"]], errors="coerce") / 1000.0,
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


def _discover_header_row(path: Path, sheet_name: str) -> int:
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
) -> pd.DataFrame:
    """Load a downloaded BIRDS EPS workbook into the canonical panel schema."""

    workbook = Path(path)
    excel = pd.ExcelFile(workbook)
    raw_parts: list[pd.DataFrame] = []
    normalized_parts: list[pd.DataFrame] = []
    errors: list[str] = []

    for sheet in excel.sheet_names:
        header_row = _discover_header_row(workbook, sheet)
        frame = pd.read_excel(workbook, sheet_name=sheet, header=header_row)
        frame = frame.dropna(how="all")
        if frame.empty:
            continue
        frame["source_sheet"] = sheet
        raw_parts.append(frame)

        if normalized:
            clean = frame.drop(columns=["source_sheet"])
            part = _normalize_birds_calibrated(clean)
            if part is None:
                try:
                    part = normalize_birds_like(clean)
                except ValueError as exc:
                    errors.append(f"{sheet}: {exc}")
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
