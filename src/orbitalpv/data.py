"""Data-loading, connector, and deterministic demonstration helpers."""

from space_pv_connectors import (
    CelesTrakConnector,
    load_table,
    make_demo_telemetry,
    normalize_birds_like,
)


def fetch_celestrak_omm(catnr: int) -> dict[str, object]:
    """Fetch the first CelesTrak OMM record for a NORAD catalog number.

    This helper requires network access. Persist the returned record when
    reproducibility matters.
    """
    with CelesTrakConnector() as connector:
        records = connector.fetch_gp(catnr=catnr)
    if not records:
        raise LookupError(f"No CelesTrak OMM record found for NORAD {catnr}")
    return records[0]


__all__ = [
    "CelesTrakConnector",
    "fetch_celestrak_omm",
    "load_table",
    "make_demo_telemetry",
    "normalize_birds_like",
]
