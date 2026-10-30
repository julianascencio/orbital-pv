"""Calibrated on-orbit solar-array telemetry from the Flying Laptop mission."""

from __future__ import annotations

import json
import re
import tarfile
from dataclasses import asdict
from datetime import datetime
from hashlib import md5, sha256
from pathlib import Path, PurePosixPath

import numpy as np
import pandas as pd

from .http_base import DownloadReceipt, HttpConnector

_DATASET_DOI = "10.18419/darus-451"
_DESCRIPTION_DOI = "10.18419/darus-456"
_PANELS = {"00": "right", "01": "left", "02": "center", "03": "test"}
_PACKET_NAME = re.compile(r"hk4900_\d{4}-\d{2}(?:_\d+)?\.csv")
_VALUE_COLUMNS = {f"PST{quantity}{code}" for code in _PANELS for quantity in ("CUR", "VLT")}


def _validate_month(month: str) -> None:
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("month must have the form YYYY-MM")
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise ValueError("month must be a valid calendar month in YYYY-MM form") from exc


def _provenance_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.provenance.json")


def _utc_bound(value: str | pd.Timestamp | None) -> pd.Timestamp | None:
    if value is None:
        return None
    bound = pd.Timestamp(value)
    if not isinstance(bound, pd.Timestamp):
        raise ValueError("Time bounds must be valid timestamps")
    return bound.tz_localize("UTC") if bound.tzinfo is None else bound.tz_convert("UTC")


class FlyingLaptopConnector(HttpConnector):
    """Retrieve CC BY 4.0 Flying Laptop monthly archives from DaRUS.

    The archive contains many housekeeping packets. The normalizer reads only
    packet 4900, whose calibrated array currents and voltages have documented
    units of A and V. Downloads retain a checksum-bearing provenance sidecar.
    """

    BASE_URL = "https://darus.uni-stuttgart.de"
    DATASET_DOI = _DATASET_DOI

    def download_month(self, month: str, destination: str | Path) -> DownloadReceipt:
        """Download one YYYY-MM archive after checking its catalog checksum."""
        _validate_month(month)
        response = self._client.get(
            f"{self.BASE_URL}/api/datasets/:persistentId/",
            params={"persistentId": f"doi:{self.DATASET_DOI}"},
        )
        response.raise_for_status()
        version = response.json()["data"]["latestVersion"]
        filename = f"FLP_TM_HK_{month}.tar.bz2"
        matches = [
            entry["dataFile"]
            for entry in version["files"]
            if entry["dataFile"]["filename"] == filename
        ]
        if len(matches) != 1:
            raise LookupError(f"No unique Flying Laptop archive found for {month}")
        file_metadata = matches[0]
        file_id = file_metadata["id"]
        if isinstance(file_id, bool) or not isinstance(file_id, int) or file_id <= 0:
            raise ValueError("Flying Laptop catalog contains an invalid datafile ID")
        url = f"{self.BASE_URL}/api/access/datafile/{file_id}"
        response = self._client.get(url)
        response.raise_for_status()
        content = response.content
        checksum = file_metadata.get("checksum", {})
        algorithm = str(checksum.get("type", "")).upper()
        if algorithm == "MD5":
            actual_checksum = md5(content, usedforsecurity=False).hexdigest()
        elif algorithm == "SHA-256":
            actual_checksum = sha256(content).hexdigest()
        else:
            raise ValueError("Flying Laptop catalog does not supply a supported checksum")
        if actual_checksum != str(checksum.get("value", "")).lower():
            raise ValueError("Flying Laptop download does not match its catalog checksum")
        if not content.startswith(b"BZh"):
            raise ValueError("Flying Laptop download is not a bzip2 archive")

        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        receipt = self.receipt("Flying Laptop / DaRUS", url, content, path=path)
        metadata = {
            **asdict(receipt),
            "dataset_doi": self.DATASET_DOI,
            "description_doi": _DESCRIPTION_DOI,
            "license": "CC BY 4.0",
            "month": month,
            "source_filename": filename,
            "datafile_id": file_id,
            "dataset_version": f"{version.get('versionNumber')}.{version.get('versionMinorNumber')}",
            "catalog_checksum": checksum,
        }
        _provenance_path(path).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return receipt

    def download_frame(
        self,
        month: str,
        destination: str | Path,
        *,
        time_min: str | pd.Timestamp | None = None,
        time_max: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Download a month and normalize the requested UTC time interval."""
        receipt = self.download_month(month, destination)
        return load_flying_laptop_power(
            receipt.path or destination, time_min=time_min, time_max=time_max
        )


def load_flying_laptop_power(
    path: str | Path,
    *,
    time_min: str | pd.Timestamp | None = None,
    time_max: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Read calibrated solar-array V, I and computed power from a local archive.

    ``time_min`` is inclusive and ``time_max`` exclusive; naive bounds are UTC.
    Timestamps are the source's Unix epoch milliseconds in UTC, identifying
    packet generation. The source documents up to 400 ms of additional sensor
    acquisition delay. Missing/invalid readings remain missing and are omitted
    per voltage/current pair; signed sensor values are not clipped.

    Four panel identifiers are preserved: ``right``, ``left``, ``center`` and
    ``test``. Here ``test`` is the spacecraft's experimental array channel,
    not a separate ground-test recording. Power is computed as V times I;
    no independently transmitted power measurement is implied.

    The reader streams only matching packet 4900 members, never extracting
    archive paths to disk. A downloaded provenance sidecar, when present, is
    verified against the local archive. Source metadata is returned in attrs.
    """
    start, stop = _utc_bound(time_min), _utc_bound(time_max)
    if start is not None and stop is not None and start >= stop:
        raise ValueError("time_min must be earlier than time_max")
    archive_path = Path(path)
    digest = sha256(archive_path.read_bytes()).hexdigest()
    provenance: dict[str, object] = {
        "dataset_doi": _DATASET_DOI,
        "description_doi": _DESCRIPTION_DOI,
        "license": "CC BY 4.0",
        "sha256": digest,
        "timestamp_basis": "UTC packet generation; Unix epoch milliseconds",
        "sensor_acquisition_delay_max_ms": 400,
    }
    sidecar = _provenance_path(archive_path)
    if sidecar.exists():
        downloaded_metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        if downloaded_metadata.get("sha256") != digest:
            raise ValueError("Flying Laptop cache does not match its provenance checksum")
        provenance.update(downloaded_metadata)

    parts: list[pd.DataFrame] = []
    source_files: list[str] = []
    try:
        with tarfile.open(archive_path, mode="r|bz2") as archive:
            for member in archive:
                if not member.isfile() or not _PACKET_NAME.fullmatch(
                    PurePosixPath(member.name).name
                ):
                    continue
                source_files.append(member.name)
                stream = archive.extractfile(member)
                if stream is None:
                    continue
                with stream:
                    raw = pd.read_csv(
                        stream,
                        sep="\t",
                        usecols=lambda column: column in _VALUE_COLUMNS | {"timestamp"},
                    )
                missing = (_VALUE_COLUMNS | {"timestamp"}) - set(raw.columns)
                if missing:
                    raise ValueError(
                        f"Flying Laptop packet {member.name} lacks columns: {sorted(missing)}"
                    )
                timestamp = pd.to_datetime(
                    pd.to_numeric(raw["timestamp"], errors="coerce"),
                    unit="ms",
                    utc=True,
                    errors="coerce",
                )
                if len(raw) and timestamp.isna().all():
                    raise ValueError(
                        f"Flying Laptop packet {member.name} has no valid epoch-ms timestamps"
                    )
                selected = timestamp.notna()
                if start is not None:
                    selected &= timestamp >= start
                if stop is not None:
                    selected &= timestamp < stop
                raw = raw.loc[selected]
                for code, panel_id in _PANELS.items():
                    panel = pd.DataFrame(
                        {
                            "timestamp": timestamp.loc[selected],
                            "panel_id": panel_id,
                            "voltage_v": pd.to_numeric(raw[f"PSTVLT{code}"], errors="coerce"),
                            "current_a": pd.to_numeric(raw[f"PSTCUR{code}"], errors="coerce"),
                            "satellite": "Flying Laptop",
                            "source_packet": "4900",
                            "source_file": member.name,
                        }
                    )
                    panel = panel[
                        np.isfinite(panel["voltage_v"]) & np.isfinite(panel["current_a"])
                    ].copy()
                    panel["power_w"] = panel["voltage_v"] * panel["current_a"]
                    parts.append(panel)
    except (tarfile.TarError, EOFError) as exc:
        raise ValueError("Could not read the Flying Laptop bzip2 tar archive") from exc
    if not source_files:
        raise ValueError("Flying Laptop archive has no packet 4900 CSV members")
    if not parts:
        raise ValueError("Flying Laptop archive contains no readable packet 4900 data")
    result = (
        pd.concat(parts, ignore_index=True)
        .sort_values(["panel_id", "timestamp"])
        .reset_index(drop=True)
    )
    provenance["source_files"] = source_files
    result.attrs.update(provenance)
    return result


__all__ = ["FlyingLaptopConnector", "load_flying_laptop_power"]
