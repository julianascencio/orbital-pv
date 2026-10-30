"""Data-loading, connector, and deterministic demonstration helpers."""

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from space_pv_connectors import (
    BirdsEPSConnector,
    CelesTrakConnector,
    FlyingLaptopConnector,
    LisirdConnector,
    NoaaSwpcConnector,
    OpsSatADConnector,
    load_birds_eps_workbook,
    load_flying_laptop_power,
    load_goes_integral_particle_flux,
    load_opssat_segments,
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


def fetch_flying_laptop_power(
    month: str,
    destination: str | Path,
    *,
    time_min: str | pd.Timestamp | None = None,
    time_max: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Download a Flying Laptop month and normalize its measured array V/I.

    Power is computed from each documented voltage/current pair. UTC packet
    timestamps and four array identities are preserved. Bounds are inclusive
    at ``time_min`` and exclusive at ``time_max``. For offline reuse, call
    :func:`load_flying_laptop_power` on the downloaded archive.
    """
    with FlyingLaptopConnector(timeout_s=120.0) as connector:
        return connector.download_frame(month, destination, time_min=time_min, time_max=time_max)


def fetch_opssat_segments(
    destination: str | Path,
    *,
    channels: Sequence[str] | None = None,
    split: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Fetch checksum-verified original OPS-SAT telemetry and expert labels.

    Values retain their published scale; the source supplies no engineering
    unit declaration. Segment IDs and the provider's train/test split remain
    intact. Photodiode measurements are not panel electrical power.
    """
    with OpsSatADConnector() as connector:
        return connector.download_frame(
            destination, channels=channels, split=split, refresh=refresh
        )


__all__ = [
    "BirdsEPSConnector",
    "CelesTrakConnector",
    "FlyingLaptopConnector",
    "LisirdConnector",
    "NoaaSwpcConnector",
    "OpsSatADConnector",
    "fetch_birds_eps",
    "fetch_celestrak_omm",
    "fetch_flying_laptop_power",
    "fetch_opssat_segments",
    "load_birds_eps_workbook",
    "load_flying_laptop_power",
    "load_goes_integral_particle_flux",
    "load_opssat_segments",
    "load_table",
    "make_demo_telemetry",
    "normalize_birds_like",
]
