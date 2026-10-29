"""Data-loading, connector, and deterministic demonstration helpers."""

from pathlib import Path

import pandas as pd

from space_pv_connectors import (
    BirdsEPSConnector,
    CelesTrakConnector,
    load_birds_eps_workbook,
    load_table,
    make_demo_telemetry,
    normalize_birds_like,
)


def fetch_celestrak_omm(catnr: int) -> dict[str, object]:
    """Fetch the first CelesTrak OMM record for a NORAD catalog number."""

    with CelesTrakConnector() as connector:
        records = connector.fetch_gp(catnr=catnr)
    if not records:
        raise LookupError(f"No CelesTrak OMM record found for NORAD {catnr}")
    return records[0]


def fetch_birds_eps(
    satellite: str,
    destination: str | Path,
) -> pd.DataFrame:
    """Download and normalize real on-orbit BIRDS EPS telemetry."""

    with BirdsEPSConnector() as connector:
        return connector.download_frame(satellite, destination, normalized=True)


__all__ = [
    "BirdsEPSConnector",
    "CelesTrakConnector",
    "fetch_birds_eps",
    "fetch_celestrak_omm",
    "load_birds_eps_workbook",
    "load_table",
    "make_demo_telemetry",
    "normalize_birds_like",
]
