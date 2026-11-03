"""Public InSight solar-energy/current data with source-bound verified caches."""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import asdict
from hashlib import md5, sha256
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd

from .http_base import HttpConnector

INSIGHT_DATA_DOI = "https://doi.org/10.7281/T1EPKRKR"


def parse_insight_energy(content: bytes) -> pd.DataFrame:
    """Read the native JHU Wh/sol table (operational estimates, not a wattmeter)."""
    frame = pd.read_csv(io.BytesIO(content))
    if frame.columns.tolist() != ["sol", "Available Array Energy (Whr)"]:
        raise ValueError("unexpected InSight energy CSV schema")
    frame.columns = ["sol", "estimated_array_energy_wh"]
    for name in frame:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    if (
        frame.empty
        or not np.all(np.isfinite(frame))
        or (frame.sol < 0).any()
        or (frame.sol % 1 != 0).any()
        or frame.sol.duplicated().any()
        or (frame.estimated_array_energy_wh < 0).any()
    ):
        raise ValueError("invalid energy data, sol identifiers or duplicate sols")
    frame["sol"] = frame.sol.astype(int)
    frame.attrs.update(
        source=INSIGHT_DATA_DOI,
        units="Wh per Martian sol",
        measurement_kind="operational estimate from fitted array current and voltage",
    )
    return frame.sort_values("sol").reset_index(drop=True)


def parse_insight_currents(content: bytes) -> pd.DataFrame:
    """Read a native Lorenz ASCII file; preserve gaps and both DBR currents.

    UTC is the header timestamp plus elapsed SI seconds. The archive's LMST
    and LTST strings are preserved; only LTST is additionally converted to
    Mars clock hours. DBR string currents are not total array output power.
    """
    lines = content.decode("utf-8-sig").splitlines()
    match = re.fullmatch(
        r"InSight Sol\s+(\d+)\s+([\d.]+)\s+s = UTC\s+(\S+)\s*", lines[0] if lines else ""
    )
    if (
        match is None
        or len(lines) < 5
        or "SA771(+Y,E)" not in lines[2]
        or "SA791(-Y,W)" not in lines[2]
    ):
        raise ValueError("unexpected InSight current header")
    frame = pd.read_csv(io.StringIO("\n".join(lines[4:])), sep=r"\s+", header=None)
    if frame.shape[1] != 5 or frame.empty:
        raise ValueError("unexpected InSight current table")
    frame.columns = ["elapsed_seconds", "lmst", "ltst", "sa771_current_a", "sa791_current_a"]
    numeric = ["elapsed_seconds", "sa771_current_a", "sa791_current_a"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="raise")
    if not np.all(np.isfinite(frame[numeric])) or (np.diff(frame.elapsed_seconds) <= 0).any():
        raise ValueError("current samples must be finite and time ordered")
    elapsed = frame.elapsed_seconds - float(match[2])
    if (elapsed < 0).any():
        raise ValueError("sample time precedes header reference")
    frame["timestamp"] = pd.Timestamp(match[3], tz="UTC") + pd.to_timedelta(elapsed, unit="s")
    clocks = frame.ltst.str.extract(r"^(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)$").astype(float)
    if clocks.isna().any().any() or (clocks[0] >= 24).any() or (clocks[[1, 2]] >= 60).any().any():
        raise ValueError("invalid LTST clock")
    frame["ltst_h"] = clocks[0] + clocks[1] / 60 + clocks[2] / 3600
    frame["sol"] = int(match[1])
    frame.attrs.update(
        source=INSIGHT_DATA_DOI,
        current_units="A",
        gap_policy="preserve; never interpolate",
        measurement_kind="hardwired DBR strings, not whole-array power",
    )
    return frame


class _MarsDownloadConnector(HttpConnector):
    def _bytes(
        self,
        url: str,
        *,
        cache_path: str | Path | None,
        source: str,
        expected_md5: str | None = None,
    ) -> tuple[bytes, dict]:
        path = Path(cache_path) if cache_path is not None else None
        sidecar = path.with_suffix(path.suffix + ".meta.json") if path is not None else None
        if path is not None and path.exists():
            if sidecar is None or not sidecar.exists():
                raise ValueError("Mars cache requires its provenance sidecar")
            content = path.read_bytes()
            receipt = json.loads(sidecar.read_text())
            if (
                receipt.get("request_url") != url
                or receipt.get("sha256") != sha256(content).hexdigest()
            ):
                raise ValueError("Mars cache query or SHA-256 mismatch")
        else:
            response = self._client.get(url)
            response.raise_for_status()
            content = response.content
            receipt = {
                **asdict(self.receipt(source, str(response.url), content)),
                "request_url": url,
            }
        if expected_md5 and md5(content, usedforsecurity=False).hexdigest() != expected_md5:
            raise ValueError("download differs from the published version's MD5")
        if path is not None and sidecar is not None and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            sidecar.write_text(json.dumps(receipt, indent=2) + "\n")
        return content, receipt


class InSightSolarConnector(_MarsDownloadConnector):
    """JHU Dataverse v1.0 of DOI 10.7281/T1EPKRKR, CC BY 4.0.

    All five native current archives through end of mission are supported.
    Files are pinned to observed Dataverse IDs and publisher checksums. No
    authentication is needed. A source revision fails closed until reviewed.
    """

    API = "https://archive.data.jhu.edu/api"
    ARCHIVES: ClassVar[dict[str, tuple[int, str]]] = {
        "0000-0099": (16255, "3cef99b875e09740142ad985b5591b33"),
        "0100-0199": (16254, "59b2fc4332a8793ebc2512cbf85c3688"),
        "0200-0499": (16258, "1fe55b20da36f4a3f2005dbebc4e430e"),
        "0500-0688": (16259, "b865d40cfcf4bbe12d6f023572cccc45"),
        "0689-EOM": (16257, "fc7f44c0df495d0b4ac9566508351147"),
    }

    def catalogue(self) -> dict:
        """Inspect current publisher metadata; downloads remain version-pinned."""
        response = self._client.get(
            f"{self.API}/datasets/:persistentId/", params={"persistentId": "doi:10.7281/T1EPKRKR"}
        )
        response.raise_for_status()
        return response.json()["data"]

    def daily_energy(self, *, cache_path: str | Path | None = None) -> pd.DataFrame:
        """Fetch the published 200 daily operational energy estimates."""
        content, receipt = self._bytes(
            f"{self.API}/access/datafile/16253",
            cache_path=cache_path,
            source=INSIGHT_DATA_DOI,
            expected_md5="dfa0f254b524f5777dd5036f40adb9e9",
        )
        frame = parse_insight_energy(content)
        frame.attrs["provenance"] = receipt
        return frame

    def currents(
        self,
        *,
        archive: str = "0000-0099",
        sols: list[int] | None = None,
        invalid_files: str = "raise",
        cache_path: str | Path | None = None,
    ) -> pd.DataFrame:
        """Fetch an archive and parse selected sols, without extracting files.

        Missing requested sols raise an error. Some native files contain byte
        corruption. By default a malformed file fails the request; explicit
        ``invalid_files="report"`` skips whole malformed files and lists each
        one in ``attrs["rejected_files"]`` without repairing measured values. Gaps within returned sols stay
        missing; do not integrate across sleep periods to infer daily energy.
        """
        if archive not in self.ARCHIVES:
            raise ValueError(f"unknown archive; choose from {list(self.ARCHIVES)}")
        if sols is not None and (
            not sols or any(isinstance(s, bool) or not isinstance(s, int) or s < 0 for s in sols)
        ):
            raise ValueError("sols must contain nonnegative integer sol identifiers")
        identifier, checksum = self.ARCHIVES[archive]
        content, receipt = self._bytes(
            f"{self.API}/access/datafile/{identifier}",
            cache_path=cache_path,
            source=INSIGHT_DATA_DOI,
            expected_md5=checksum,
        )
        if invalid_files not in {"raise", "report"}:
            raise ValueError("invalid_files must be 'raise' or 'report'")
        rejected = []
        frames = []
        with zipfile.ZipFile(io.BytesIO(content)) as zipped:
            members = [
                m
                for m in zipped.infolist()
                if m.filename.lower().endswith(".txt") and not m.filename.startswith("__MACOSX/")
            ]
            if sum(m.file_size for m in members) > 150_000_000:
                raise ValueError("uncompressed archive exceeds 150 MB limit")
            for member in members:
                match = re.fullmatch(r"Solar_(\d+)-(\d+)\.txt", Path(member.filename).name)
                if not match or match[1] != match[2]:
                    raise ValueError(f"unsupported current archive member: {member.filename}")
                sol = int(match[1])
                if sols is None or sol in sols:
                    try:
                        frame = parse_insight_currents(zipped.read(member))
                    except (ValueError, UnicodeError) as exc:
                        if invalid_files == "raise":
                            raise ValueError(
                                f"Invalid source file {member.filename}: {exc}"
                            ) from exc
                        rejected.append({"file": member.filename, "reason": str(exc)})
                        continue
                    if not frame.sol.eq(sol).all():
                        raise ValueError("sol disagrees with archive filename")
                    frames.append(frame)
        if not frames:
            raise ValueError("no requested current records found")
        result = pd.concat(frames, ignore_index=True).sort_values(["sol", "timestamp"])
        if sols is not None and set(sols) != set(result.sol):
            raise ValueError("one or more requested sols are missing")
        if result.duplicated(["sol", "timestamp"]).any():
            raise ValueError("duplicate current timestamps")
        result.attrs.update(frames[0].attrs)
        result.attrs["provenance"] = receipt
        result.attrs["rejected_files"] = rejected
        return result.reset_index(drop=True)


INSIGHT_OPACITY_BASE = "https://atmos.nmsu.edu/PDS/review/PDS4/insight_tau_bundle/data"


def parse_insight_opacity(content: bytes) -> pd.DataFrame:
    """Read the PDS nsyt_tau v1.0 seven-field CSV, retaining uncertainties.

    Schema verified against ``nsyt_tau.xml``. Sol is fractional true solar
    time; opacity is at 600 nm. Never silently convert it to broadband tau.
    The provider currently links a review-directory product: retain that status.
    """
    frame = pd.read_csv(io.BytesIO(content), header=None)
    if frame.shape[1] != 7 or frame.empty:
        raise ValueError("expected seven PDS InSight opacity fields")
    frame.columns = [
        "product_id",
        "sol_ltst",
        "lmst_h",
        "solar_longitude_deg",
        "optical_depth_600nm",
        "optical_depth_sigma",
        "relative_fit_sigma",
    ]
    for name in frame.columns[1:]:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    if (
        not np.all(np.isfinite(frame.iloc[:, 1:]))
        or frame.product_id.duplicated().any()
        or (frame.sol_ltst < 0).any()
        or (frame.optical_depth_600nm < 0).any()
        or (frame.optical_depth_sigma < 0).any()
        or (frame.relative_fit_sigma < 0).any()
        or ((frame.lmst_h < 0) | (frame.lmst_h >= 24)).any()
        or ((frame.solar_longitude_deg < 0) | (frame.solar_longitude_deg >= 360)).any()
    ):
        raise ValueError("invalid PDS InSight opacity fields")
    frame["wavelength_nm"] = 600
    frame.attrs.update(
        source=f"{INSIGHT_OPACITY_BASE}/nsyt_tau.csv",
        logical_identifier="urn:nasa:pds:insight_cameras_tau:data_derived:nsyt_tau::1.0",
        archive_status="provider-linked review directory; not asserted final",
        measurement_kind="camera-derived atmospheric opacity",
    )
    return frame.sort_values("sol_ltst").reset_index(drop=True)


class InSightOpacityConnector(_MarsDownloadConnector):
    """PDS camera-derived 600-nm optical depth, with sigma and fit uncertainty.

    This is the product linked by the PDS Atmospheres InSight opacity landing
    page. Its URL is in the review tree; no final-archive status is inferred.
    The pinned MD5 is from the version 1.0 PDS4 XML label.
    """

    def optical_depth(self, *, cache_path: str | Path | None = None) -> pd.DataFrame:
        """Download the native table; no averaging, gap filling or extrapolation."""
        content, receipt = self._bytes(
            f"{INSIGHT_OPACITY_BASE}/nsyt_tau.csv",
            cache_path=cache_path,
            source="https://doi.org/10.17189/dc8r-ag55",
            expected_md5="d767af6c8a1654faa69e325dcc7bf762",
        )
        frame = parse_insight_opacity(content)
        frame.attrs["provenance"] = receipt
        return frame
