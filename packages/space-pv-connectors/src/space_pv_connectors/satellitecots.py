"""Pinned BUPT-1 platform telemetry from the SatelliteCOTS research archive.

The source has no explicit redistribution licence. Download into a local cache;
do not bundle its raw telemetry with OrbitalPV. Naive source clocks stay naive
unless the caller supplies a timezone. MPPT input, controller output and bus
load are distinct measurement boundaries, none an available-MPP measurement.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .http_base import DownloadReceipt, HttpConnector

SATELLITECOTS_COMMIT = "951b41521351d535b7c2354916d9c4991602e8c7"
_BASE = (
    "https://raw.githubusercontent.com/TiansuanConstellation/"
    f"MobiCom24-SatelliteCOTS/{SATELLITECOTS_COMMIT}"
)
_SOURCES = {
    "common": (
        "CommonData-Telemetries/telemetry_all.csv.zip",
        "5d761d0bb65730cdbdb364f9c8706e9469bbbc6049cc0ed0b22d95ead8d656fa",
        80_884_357,
    ),
    "multiplexed": (
        "Energy-ShortTerm/telemetries/all.csv",
        "817fa3bb188acef2923436c5e72a5e64383598028df97976a4d375c2d2b39dec",
        499_260,
    ),
}
Source = Literal["common", "multiplexed"]


def _digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _source(source: Source) -> tuple[str, str, int]:
    if source not in _SOURCES:
        raise ValueError("source must be 'common' or 'multiplexed'")
    return _SOURCES[source]


class SatelliteCOTSConnector(HttpConnector):
    """Download the authors' original files, pinned by commit and SHA-256."""

    def download(
        self, destination: str | Path, *, source: Source = "common", refresh: bool = False
    ) -> DownloadReceipt:
        relative, expected, size = _source(source)
        path = Path(destination)
        sidecar = path.with_name(path.name + ".provenance.json")
        url = f"{_BASE}/{relative}"
        if path.exists() and not refresh:
            if _digest(path) != expected:
                raise ValueError("BUPT-1 cache does not match the pinned source checksum")
            if not sidecar.exists():
                raise ValueError("Verified cache lacks provenance; use refresh=True to retrieve it")
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            if meta.get("sha256") != expected or meta.get("url") != url:
                raise ValueError("BUPT-1 cache provenance does not match the pinned source")
            return DownloadReceipt(
                **{key: meta[key] for key in DownloadReceipt.__dataclass_fields__}
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".download")
        digest = sha256()
        downloaded = 0
        try:
            with self._client.stream("GET", url) as response, temporary.open("wb") as stream:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    downloaded += len(chunk)
                    if downloaded > size:
                        raise ValueError("BUPT-1 download exceeds the pinned source size")
                    stream.write(chunk)
                    digest.update(chunk)
            if downloaded != size or digest.hexdigest() != expected:
                raise ValueError("BUPT-1 download does not match the pinned source checksum")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        # Receipt timestamp is retrieval time, never a measurement timestamp.
        receipt = self.receipt("BUPT-1 / SatelliteCOTS", url, b"", path=path)
        receipt = DownloadReceipt(
            receipt.source, url, receipt.retrieved_at, expected, downloaded, str(path)
        )
        sidecar.write_text(
            json.dumps(
                {
                    **asdict(receipt),
                    "source_commit": SATELLITECOTS_COMMIT,
                    "source_schema": source,
                    "source_paper": "https://arxiv.org/abs/2401.03435",
                    "license": "Not declared in the source repository",
                    "source_timezone": "Unspecified",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return receipt


def _timestamps(values: pd.Series, source_timezone: str | None) -> pd.Series:
    times = pd.to_datetime(values, errors="coerce", format="mixed")
    if len(times) and times.isna().all():
        raise ValueError("BUPT-1 data has no readable source timestamps")
    if getattr(times.dt, "tz", None) is not None:
        return times.dt.tz_convert("UTC")
    if source_timezone is not None:
        return times.dt.tz_localize(
            source_timezone, ambiguous="raise", nonexistent="raise"
        ).dt.tz_convert("UTC")
    return times


def normalize_bupt1_telemetry(
    raw: pd.DataFrame, *, source: Source = "common", source_timezone: str | None = None
) -> pd.DataFrame:
    """Normalize units without interpolating or demultiplexing measurements.

    The common archive supplies separate MPPT1/2 and battery1/2 columns. The
    short-term source cycles through hardware groups; its group-specific power
    must not be mistaken for simultaneous whole-spacecraft PV power. Duplicate
    source clocks and signed sensor offsets remain visible. Zero temperature
    is retained because zero is not documented as a universal missing sentinel.
    """
    _source(source)
    required = {"Time", "Total_U", "Total_I"}
    if source == "common":
        required |= {f"MPPT{n}_{q}" for n in (1, 2) for q in ("Uin", "Iin", "Iout")}
    else:
        required |= {"MPPT_Group", "MPPT_Uin", "MPPT_Iin", "MPPT_Iout", "BATTERY_Group"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"BUPT-1 {source} source lacks columns: {sorted(missing)}")
    out = pd.DataFrame(index=raw.index)
    out["source_row"] = raw.index
    out["source_timestamp"] = raw["Time"].astype(str)
    out["timestamp"] = _timestamps(raw["Time"], source_timezone)

    def numeric(column: str) -> pd.Series:
        values = pd.to_numeric(raw[column], errors="coerce")
        return values.where(np.isfinite(values))

    out["bus_voltage_v"] = numeric("Total_U") / 1000
    out["bus_current_a"] = numeric("Total_I") / 1000
    out["bus_power_w"] = out["bus_voltage_v"] * out["bus_current_a"]
    if source == "common":
        for number in (1, 2):
            prefix = f"mppt_{number}"
            for source_quantity, quantity in (
                ("Uin", "input_voltage_v"),
                ("Iin", "input_current_a"),
                ("Iout", "output_current_a"),
            ):
                out[f"{prefix}_{quantity}"] = numeric(f"MPPT{number}_{source_quantity}") / 1000
            out[f"{prefix}_input_power_w"] = (
                out[f"{prefix}_input_voltage_v"] * out[f"{prefix}_input_current_a"]
            )
            out[f"{prefix}_output_power_w"] = (
                out["bus_voltage_v"] * out[f"{prefix}_output_current_a"]
            )
            if {f"BATTERY{number}_U", f"BATTERY{number}_I"} <= set(raw.columns):
                out[f"battery_{number}_voltage_v"] = numeric(f"BATTERY{number}_U") / 1000
                out[f"battery_{number}_current_a"] = numeric(f"BATTERY{number}_I") / 1000
                out[f"battery_{number}_source_signed_power_w"] = (
                    out[f"battery_{number}_voltage_v"] * out[f"battery_{number}_current_a"]
                )
        out["pv_input_power_w"] = out[["mppt_1_input_power_w", "mppt_2_input_power_w"]].sum(
            axis=1, min_count=2
        )
        out["solar_bus_power_w"] = out[["mppt_1_output_power_w", "mppt_2_output_power_w"]].sum(
            axis=1, min_count=2
        )
        battery_columns = [f"battery_{n}_source_signed_power_w" for n in (1, 2)]
        if set(battery_columns) <= set(out.columns):
            out["battery_source_signed_power_w"] = out[battery_columns].sum(axis=1, min_count=2)
    else:
        out["mppt_group"] = numeric("MPPT_Group")
        out["battery_group"] = numeric("BATTERY_Group")
        out["group_pv_input_power_w"] = numeric("MPPT_Uin") * numeric("MPPT_Iin") / 1e6
        out["group_mppt_output_power_w"] = numeric("MPPT_Iout") * out["bus_voltage_v"] / 1000
        if {"Battery_U", "Battery_I"} <= set(raw.columns):
            out["group_battery_source_signed_power_w"] = (
                numeric("Battery_U") * numeric("Battery_I") / 1e6
            )
    for source_name, name in (
        ("I_Atlas200DK-A", "atlas_a_current_a"),
        ("I_Atlas200DK-B", "atlas_b_current_a"),
        ("I_Pi-A", "pi_a_current_a"),
        ("I_Pi-B", "pi_b_current_a"),
        ("POBC_I_5V", "pobc_current_a"),
        ("XMIT_A_12V", "transmitter_a_current_a"),
        ("XMIT_B_12V", "transmitter_b_current_a"),
    ):
        if source_name in raw:
            out[name] = numeric(source_name) / 1000
    for source_name, name in (
        ("ATLAS_A_TEMP", "atlas_a_temperature_c"),
        ("ATLAS_B_TEMP", "atlas_b_temperature_c"),
        ("PI_A_TEMP", "pi_a_temperature_c"),
    ):
        if source_name in raw:
            out[name] = numeric(source_name)
    out["valid_timestamp"] = out["timestamp"].notna()
    out["duplicate_timestamp"] = out["timestamp"].duplicated(keep=False)
    out.attrs.update(
        satellite="BUPT-1",
        schema=source,
        source_commit=SATELLITECOTS_COMMIT,
        timestamp_basis=(
            "Source-local clock; timezone unspecified"
            if source_timezone is None
            else f"Caller-supplied timezone {source_timezone}; converted to UTC"
        ),
        source_timezone=source_timezone,
        license="Not declared in the source repository",
        power_boundary="Observed operating input/output/bus power; available MPP is not observed",
        battery_sign="Source-signed V*I; source plotting code negates it for discharge",
        temperature_missing_policy="Zero values retained; no undocumented sentinel replacement",
    )
    return out.reset_index(drop=True)


def load_bupt1_telemetry(
    path: str | Path,
    *,
    source: Source = "common",
    source_timezone: str | None = None,
    time_min: str | pd.Timestamp | None = None,
    time_max: str | pd.Timestamp | None = None,
    verify_source: bool = True,
    chunksize: int = 100_000,
) -> pd.DataFrame:
    """Stream a local pinned archive, filtering inclusive/exclusive source times.

    Bounds must match the timestamp basis: naive for an unspecified source
    timezone, or timezone-aware if ``source_timezone`` is supplied. The full
    archive is large; supply a time window. No ZIP member is extracted to disk.
    Set ``verify_source=False`` only for independently provided files, which
    are then labelled unverified rather than claimed as the pinned archive.
    """
    _, expected, _ = _source(source)
    if isinstance(chunksize, bool) or not isinstance(chunksize, int) or chunksize < 1:
        raise ValueError("chunksize must be a positive integer")
    file = Path(path)
    digest = _digest(file)
    if verify_source and digest != expected:
        raise ValueError("BUPT-1 local file does not match the pinned source checksum")
    bounds = [None if value is None else pd.Timestamp(value) for value in (time_min, time_max)]
    for value in bounds:
        if value is not None and (value.tzinfo is None) != (source_timezone is None):
            raise ValueError("Time bounds must match the source timezone interpretation")
    start, stop = bounds
    if start is not None and stop is not None and start >= stop:
        raise ValueError("time_min must be earlier than time_max")
    pieces: list[pd.DataFrame] = []

    def read(stream) -> None:
        for chunk in pd.read_csv(stream, chunksize=chunksize, encoding="utf-8-sig"):
            times = _timestamps(chunk["Time"], source_timezone)
            selected = times.notna()
            if start is not None:
                selected &= times >= start
            if stop is not None:
                selected &= times < stop
            if selected.any():
                pieces.append(
                    normalize_bupt1_telemetry(
                        chunk.loc[selected], source=source, source_timezone=source_timezone
                    )
                )

    if source == "common":
        try:
            with zipfile.ZipFile(file) as archive:
                matches = [
                    item for item in archive.infolist() if item.filename == "telemetry_all.csv"
                ]
                if len(matches) != 1 or matches[0].file_size > 4_000_000_000:
                    raise ValueError("BUPT-1 archive must contain one bounded telemetry_all.csv")
                with archive.open(matches[0]) as stream:
                    read(stream)
        except zipfile.BadZipFile as exc:
            raise ValueError("BUPT-1 source is not a readable ZIP archive") from exc
    else:
        with file.open("rb") as stream:
            read(stream)
    if not pieces:
        raise ValueError("No BUPT-1 measurements in the requested interval")
    metadata = pieces[0].attrs.copy()
    result = pd.concat(pieces, ignore_index=True)
    result["duplicate_timestamp"] = result["timestamp"].duplicated(keep=False)
    result.attrs.update(
        {**metadata, "sha256": digest, "verified_source": verify_source, "source_path": str(file)}
    )
    return result


__all__ = [
    "SATELLITECOTS_COMMIT",
    "SatelliteCOTSConnector",
    "load_bupt1_telemetry",
    "normalize_bupt1_telemetry",
]
