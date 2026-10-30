"""Original, annotated OPS-SAT telemetry segments from the pinned OPSSAT-AD v2 release."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd

from .http_base import DownloadReceipt, HttpConnector

_CHANNEL_DETAILS = {
    "CADC0872": ("I_B_FB_MM_0", "magnetometer"),
    "CADC0873": ("I_B_FB_MM_1", "magnetometer"),
    "CADC0874": ("I_B_FB_MM_2", "magnetometer"),
    "CADC0884": ("I_PD1_THETA", "photodiode"),
    "CADC0886": ("I_PD2_THETA", "photodiode"),
    "CADC0888": ("I_PD3_THETA", "photodiode"),
    "CADC0890": ("I_PD4_THETA", "photodiode"),
    "CADC0892": ("I_PD5_THETA", "photodiode"),
    "CADC0894": ("I_PD6_THETA", "photodiode"),
}
_REQUIRED_COLUMNS = {
    "channel",
    "timestamp",
    "value",
    "label",
    "sampling",
    "anomaly",
    "segment",
    "train",
}


class OpsSatADConnector(HttpConnector):
    """Download the original telemetry CSV from the fixed OPSSAT-AD v2 release.

    Data are CC BY 4.0, DOI ``10.5281/zenodo.15108715``. The 19 MB CSV
    contains measured magnetometer and photodiode channels, rather than the
    separate handcrafted-feature table. No credentials are required.

    The source does not include engineering-unit declarations. Values are
    preserved in their published scale, without interpreting photodiodes as
    solar-panel current, irradiance, or generated electrical power.
    """

    URL = "https://zenodo.org/records/15108715/files/segments.csv?download=1"
    DATASET_DOI = "10.5281/zenodo.15108715"
    DATASET_VERSION = "v2"
    LICENSE = "CC-BY-4.0"
    SHA256 = "d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba"
    CHANNELS: ClassVar[frozenset[str]] = frozenset(_CHANNEL_DETAILS)

    def __init__(self, *, timeout_s: float = 120.0):
        super().__init__(timeout_s=timeout_s)

    @staticmethod
    def _receipt_path(path: Path) -> Path:
        return path.with_suffix(path.suffix + ".provenance.json")

    @classmethod
    def _verify(cls, content: bytes) -> None:
        if sha256(content).hexdigest() != cls.SHA256:
            raise ValueError(
                "OPS-SAT telemetry checksum does not match the pinned v2 release; "
                "use a separate destination or refresh=True to retrieve the original CSV."
            )

    def download(self, destination: str | Path) -> DownloadReceipt:
        """Download, verify, and preserve the source CSV and a provenance sidecar."""

        response = self._client.get(self.URL)
        response.raise_for_status()
        content = response.content
        self._verify(content)
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        receipt = self.receipt("OPSSAT-AD", self.URL, content, path=path)
        provenance = {
            **asdict(receipt),
            "dataset_doi": self.DATASET_DOI,
            "dataset_version": self.DATASET_VERSION,
            "license": self.LICENSE,
        }
        self._receipt_path(path).write_text(json.dumps(provenance, indent=2) + "\n")
        return receipt

    def download_frame(
        self,
        destination: str | Path,
        *,
        channels: Sequence[str] | None = None,
        split: str | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Load selected channels/split, reusing only checksum-verified cached data.

        ``channels`` is a sequence of source IDs, such as ``["CADC0892"]``.
        ``split`` is ``"train"``, ``"test"``, or ``None`` for both. Filtering
        keeps the source segment identifiers and the published benchmark split.
        A corrupt or different local file raises instead of silently replacing it.
        """

        _validate_filters(channels, split)
        path = Path(destination)
        if refresh or not path.exists():
            self.download(path)
        else:
            self._verify(path.read_bytes())
        frame = load_opssat_segments(path, channels=channels, split=split)
        receipt_path = self._receipt_path(path)
        if receipt_path.exists():
            provenance = json.loads(receipt_path.read_text())
            if provenance.get("sha256") == self.SHA256 and provenance.get("url") == self.URL:
                frame.attrs["download_receipt"] = provenance
        return frame


def _validate_filters(channels: Sequence[str] | None, split: str | None) -> None:
    if split not in (None, "train", "test"):
        raise ValueError("split must be 'train', 'test', or None")
    if channels is not None:
        if isinstance(channels, str) or not channels:
            raise ValueError("channels must be a nonempty sequence of source channel IDs")
        unknown = set(channels) - set(_CHANNEL_DETAILS)
        if unknown:
            raise ValueError(f"Unknown OPS-SAT channels: {sorted(unknown)}")


def load_opssat_segments(
    path: str | Path,
    *,
    channels: Sequence[str] | None = None,
    split: str | None = None,
) -> pd.DataFrame:
    """Read original OPSSAT-AD telemetry without resampling or merging segments.

    Every source column is retained. ``timestamp`` becomes a UTC datetime;
    ``value`` stays on its original published scale. Missing/nonfinite values
    are retained and marked by ``is_valid_value``; no fill value or physical
    unit is invented. ``value_unit`` explicitly records that units are absent
    from the source CSV.

    Use the source's numeric ``anomaly`` field for the expert annotation.
    The textual ``label`` column contains ``"anomaly"`` even for nominal
    segments in v2, so it must not be treated as a classification result.
    ``train`` is the fixed benchmark split, not a chronological split.

    A local subset may be loaded for offline analysis. The returned ``attrs``
    contain its checksum and whether it matches the complete pinned release.
    """

    _validate_filters(channels, split)
    source = Path(path)
    frame = pd.read_csv(source, dtype={"channel": "string", "label": "string"})
    missing = _REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Missing OPS-SAT telemetry columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("OPS-SAT telemetry file contains no measurements")
    if frame["channel"].isna().any() or not frame["channel"].isin(_CHANNEL_DETAILS).all():
        raise ValueError("OPS-SAT telemetry contains unknown or missing channel IDs")

    timestamps = pd.to_datetime(frame["timestamp"], format="ISO8601", utc=True, errors="coerce")
    if timestamps.isna().any():
        raise ValueError("OPS-SAT telemetry contains missing or invalid source timestamps")
    frame["timestamp"] = timestamps
    for name in ("value", "sampling", "anomaly", "segment", "train"):
        try:
            frame[name] = pd.to_numeric(frame[name], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"OPS-SAT {name} contains nonnumeric data") from exc
    for name in ("anomaly", "train"):
        if not frame[name].isin([0, 1]).all():
            raise ValueError(f"OPS-SAT {name} must contain only 0 or 1")
        frame[name] = frame[name].astype("int8")
    if not (np.isfinite(frame["sampling"]) & frame["sampling"].gt(0)).all():
        raise ValueError("OPS-SAT sampling periods must be finite and positive")
    if not (
        np.isfinite(frame["segment"]) & frame["segment"].ge(1) & frame["segment"].mod(1).eq(0)
    ).all():
        raise ValueError("OPS-SAT segment IDs must be positive integers")
    frame["segment"] = frame["segment"].astype("int64")
    consistency = frame.groupby("segment")[["channel", "anomaly", "train", "sampling"]].nunique()
    if np.any(consistency.to_numpy() > 1):
        raise ValueError("OPS-SAT segment metadata must be constant within each source segment")

    if channels is not None:
        frame = frame[frame["channel"].isin(channels)].copy()
    if split is not None:
        frame = frame[frame["train"].eq(int(split == "train"))].copy()
    frame["channel_name"] = frame["channel"].map(
        {key: val[0] for key, val in _CHANNEL_DETAILS.items()}
    )
    frame["sensor_type"] = frame["channel"].map(
        {key: val[1] for key, val in _CHANNEL_DETAILS.items()}
    )
    frame["is_valid_value"] = np.isfinite(frame["value"])
    frame["value_unit"] = "unspecified_source_unit"
    frame["source_doi"] = OpsSatADConnector.DATASET_DOI
    frame["dataset_version"] = OpsSatADConnector.DATASET_VERSION
    frame = frame.sort_values(["channel", "segment", "timestamp"], kind="stable").reset_index(
        drop=True
    )
    checksum = sha256(source.read_bytes()).hexdigest()
    frame.attrs.update(
        source_url=OpsSatADConnector.URL,
        source_doi=OpsSatADConnector.DATASET_DOI,
        dataset_version=OpsSatADConnector.DATASET_VERSION,
        license=OpsSatADConnector.LICENSE,
        file_sha256=checksum,
        matches_complete_release=checksum == OpsSatADConnector.SHA256,
        timestamp_basis="source_utc",
        annotation_field="anomaly",
    )
    return frame


__all__ = ["OpsSatADConnector", "load_opssat_segments"]
