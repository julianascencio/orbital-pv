from __future__ import annotations

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
    ) -> pd.DataFrame:
        """Download and load a BIRDS EPS workbook."""

        receipt = self.download(satellite, destination)
        path = Path(receipt.path or destination)
        return load_birds_eps_workbook(path, normalized=normalized)


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
            try:
                part = normalize_birds_like(frame.drop(columns=["source_sheet"]))
            except ValueError as exc:
                errors.append(f"{sheet}: {exc}")
                continue
            part["source_sheet"] = sheet
            normalized_parts.append(part)

    if normalized:
        if not normalized_parts:
            detail = "; ".join(errors) if errors else "no readable sheets"
            raise ValueError(f"Could not normalize BIRDS EPS workbook {workbook.name}: {detail}")
        return pd.concat(normalized_parts, ignore_index=True).sort_values(
            ["panel_id", "timestamp"]
        ).reset_index(drop=True)

    if not raw_parts:
        raise ValueError(f"No readable sheets found in {workbook}")
    return pd.concat(raw_parts, ignore_index=True)


__all__ = ["BirdsEPSConnector", "load_birds_eps_workbook"]
