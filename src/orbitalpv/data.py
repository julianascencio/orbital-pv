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
    *,
    campaign_year: int | None = None,
) -> pd.DataFrame:
    """Download and normalize real on-orbit BIRDS EPS telemetry.

    ``campaign_year`` explicitly dates sheet names that omit a year, without
    overriding fully dated sheets. Numeric clocks retain their elapsed seconds;
    calendar-anchored timestamps do not establish the true acquisition time.
    See :func:`load_birds_eps_workbook` for metadata and excluded test sheets.
    """

    with BirdsEPSConnector() as connector:
        return connector.download_frame(
            satellite, destination, normalized=True, campaign_year=campaign_year
        )


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
