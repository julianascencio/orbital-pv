"""NASA CERES and NOAA POES/MetOp environmental inputs.

These connectors retain provider variables, quality fields and units. Particle
flux at a POES/MetOp detector is not a solar-cell dose at another spacecraft.
CERES TOA flux needs a geometric/radiance model before use at a solar panel.

References
----------
https://ceres.larc.nasa.gov/data/
https://www.ncei.noaa.gov/products/poes-metop-space-environment-monitor
https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, ClassVar
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import pandas as pd

from .http_base import DownloadReceipt, HttpConnector


def _utc(value: str) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if pd.isna(result) or result.tzinfo is None:
        raise ValueError("Use an explicit timezone in start and end timestamps")
    return result.tz_convert("UTC")


def _xarray():
    try:
        import xarray as xr
    except ImportError as exc:
        raise ImportError(
            'Install "orbital-pv[netcdf]" to read environmental netCDF files'
        ) from exc
    return xr


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class EnvironmentalFileConnector(HttpConnector):
    """Bounded, atomic downloads with checksum receipts and verified cache reuse."""

    source = "environmental provider"
    allowed_hosts: tuple[str, ...] = ()

    def download(
        self,
        url: str,
        destination: str | Path,
        *,
        expected_sha256: str | None = None,
        bearer_token: str | None = None,
        max_bytes: int = 512 * 1024 * 1024,
    ) -> DownloadReceipt:
        """Download an explicit provider URL without embedding credentials in receipts.

        Existing files are reused only after their digest and receipt are checked.
        Remove or choose another destination to replace an unverified local file.
        """
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.allowed_hosts
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError(f"Expected an HTTPS data URL on {self.allowed_hosts}")
        if expected_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            raise ValueError("expected_sha256 must be a 64-character hexadecimal digest")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        request_fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()
        path = Path(destination)
        sidecar = path.with_suffix(path.suffix + ".receipt.json")
        if path.exists():
            if not sidecar.exists():
                raise ValueError("Refusing to reuse a file without a provenance receipt")
            saved = json.loads(sidecar.read_text(encoding="utf-8"))
            digest = _file_hash(path)
            if (
                saved.get("url") != safe_url
                or saved.get("request_url_sha256") != request_fingerprint
                or saved.get("sha256") != digest
                or saved.get("bytes") != path.stat().st_size
                or (expected_sha256 is not None and digest != expected_sha256.lower())
            ):
                raise ValueError(
                    "Cached environmental file failed provenance/checksum verification"
                )
            return DownloadReceipt(
                **{key: value for key, value in saved.items() if key != "request_url_sha256"}
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        temporary: Path | None = None
        try:
            with self._client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                # A login page with status 200 is not an environmental data file.
                if "text/html" in response.headers.get("content-type", ""):
                    raise ValueError("Provider returned HTML instead of data; check data access")
                with NamedTemporaryFile(
                    dir=path.parent, prefix=path.name + ".", delete=False
                ) as out:
                    temporary = Path(out.name)
                    digest_obj = hashlib.sha256()
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("Download exceeds max_bytes")
                        digest_obj.update(chunk)
                        out.write(chunk)
            digest = digest_obj.hexdigest()
            if size == 0:
                raise ValueError("Provider returned an empty file")
            if expected_sha256 is not None and digest != expected_sha256.lower():
                raise ValueError("Downloaded file does not match expected_sha256")
            receipt = DownloadReceipt(
                self.source, safe_url, datetime.now(UTC).isoformat(), digest, size, str(path)
            )
            temporary.replace(path)
            temporary = None
            sidecar.write_text(
                json.dumps({**asdict(receipt), "request_url_sha256": request_fingerprint}, indent=2)
                + "\n",
                encoding="utf-8",
            )
            return receipt
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


class CeresConnector(EnvironmentalFileConnector):
    """Discover exact CERES collections through NASA CMR and download selected files.

    Supply the collection short name explicitly: different editions and time
    aggregations are scientifically different products. Earthdata credentials
    may be needed by the file host; catalog discovery is public.
    """

    source = "NASA CERES"
    allowed_hosts = (
        "asdc.larc.nasa.gov",
        "opendap.larc.nasa.gov",
        "ceres-tool.larc.nasa.gov",
        "data.asdc.earthdata.nasa.gov",
    )
    SEARCH_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"

    def collections(
        self,
        *,
        short_name_pattern: str = "CER_SYN1deg*",
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Discover current CMR short names and separate edition/version IDs.

        NASA's cloud migration changed catalog identifiers. A product title
        containing ``_Edition4B`` need not have that suffix in its CMR short name.
        """
        if not short_name_pattern.startswith("CER_") or not 1 <= max_results <= 2000:
            raise ValueError("Use a CER_ collection pattern and max_results in 1..2000")
        response = self._client.get(
            "https://cmr.earthdata.nasa.gov/search/collections.json",
            params={
                "short_name": short_name_pattern,
                "options[short_name][pattern]": "true",
                "page_size": max_results,
            },
        )
        response.raise_for_status()
        entries = response.json().get("feed", {}).get("entry")
        if not isinstance(entries, list):
            raise ValueError("CMR collection response lacks feed.entry")
        total = response.headers.get("CMR-Hits")
        if (total is not None and int(total) > max_results) or (
            total is None and len(entries) == max_results
        ):
            raise ValueError("Narrow short_name_pattern to avoid truncating the collection catalog")
        return [
            {
                "collection_id": row.get("id"),
                "short_name": row.get("short_name"),
                "version": row.get("version_id"),
                "title": row.get("title"),
            }
            for row in entries
        ]

    def search(
        self,
        *,
        short_name: str,
        version: str,
        start: str,
        end: str,
        bounding_box: tuple[float, float, float, float] | None = None,
        page_size: int = 100,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        """Return granule metadata and direct-data URLs, failing on truncation."""
        first, last = _utc(start), _utc(end)
        if first >= last:
            raise ValueError("start must precede end")
        if not short_name.startswith("CER_") or not version.strip():
            raise ValueError("Specify a CER_ collection short_name and explicit version")
        if not 1 <= page_size <= 2000 or max_pages < 1:
            raise ValueError("page_size must be 1..2000 and max_pages positive")
        params: dict[str, Any] = {
            "short_name": short_name,
            "version": version,
            "temporal": f"{first.isoformat()},{last.isoformat()}",
            "page_size": page_size,
        }
        if bounding_box is not None:
            west, south, east, north = bounding_box
            if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                raise ValueError(
                    "bounding_box must be (west, south, east, north), without wrapping"
                )
            params["bounding_box"] = ",".join(str(v) for v in bounding_box)
        result: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            params["page_num"] = page
            response = self._client.get(self.SEARCH_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            entries = payload.get("feed", {}).get("entry")
            if not isinstance(entries, list):
                raise ValueError("CMR response lacks feed.entry")
            for entry in entries:
                data_urls = [
                    link["href"]
                    for link in entry.get("links", [])
                    if link.get("rel", "").endswith("/data#")
                    and link.get("href", "").startswith("https://")
                    and not link.get("inherited", False)
                ]
                result.append(
                    {
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "time_start": entry.get("time_start"),
                        "time_end": entry.get("time_end"),
                        "short_name": short_name,
                        "version": version,
                        "data_urls": data_urls,
                    }
                )
            total = response.headers.get("CMR-Hits")
            if len(entries) < page_size or (total is not None and len(result) >= int(total)):
                return result
        raise ValueError(
            "CMR search reached max_pages; narrow the query to avoid silent truncation"
        )


class PoesMetopConnector(EnvironmentalFileConnector):
    """Download documented NCEI daily SEM-2 Level-1b files.

    Instrument availability varies by date. Missing provider files raise the
    original HTTP error; no fabricated observations or nearby-day substitution.
    """

    source = "NOAA NCEI POES/MetOp SEM-2"
    allowed_hosts = ("www.ncei.noaa.gov", "data.ngdc.noaa.gov", "www.ngdc.noaa.gov")
    BASE_URL = "https://www.ncei.noaa.gov/data/poes-metop-space-environment-monitor/access/l1b"
    SPACECRAFT: ClassVar[dict[str, str]] = {
        "noaa15": "n15",
        "noaa16": "n16",
        "noaa17": "n17",
        "noaa18": "n18",
        "noaa19": "n19",
        "metop01": "m01",
        "metop02": "m02",
        "metop03": "m03",
    }

    @classmethod
    def daily_url(cls, spacecraft: str, day: str | date, *, version: str = "v01r00") -> str:
        if spacecraft not in cls.SPACECRAFT:
            raise ValueError(f"spacecraft must be one of {tuple(cls.SPACECRAFT)}")
        if not re.fullmatch(r"v\d{2}r\d{2}", version):
            raise ValueError("version must have the form v01r00")
        day_value = date.fromisoformat(day) if isinstance(day, str) else day
        if isinstance(day_value, datetime) or not isinstance(day_value, date):
            raise ValueError("day must be a date or YYYY-MM-DD string")
        code = cls.SPACECRAFT[spacecraft]
        return (
            f"{cls.BASE_URL}/{version}/{day_value.year}/{spacecraft}/"
            f"poes_{code}_{day_value:%Y%m%d}_proc.nc"
        )

    def fetch_day(
        self,
        spacecraft: str,
        day: str | date,
        destination: str | Path,
        *,
        version: str = "v01r00",
        expected_sha256: str | None = None,
    ) -> DownloadReceipt:
        return self.download(
            self.daily_url(spacecraft, day, version=version),
            destination,
            expected_sha256=expected_sha256,
        )


def inspect_environment_netcdf(path: str | Path) -> dict[str, dict[str, Any]]:
    """Inspect provider variable names/dimensions/units before selecting channels."""
    xr = _xarray()
    with xr.open_dataset(path, decode_times=False) as dataset:
        return {
            str(name): {
                "dimensions": list(variable.dims),
                "shape": list(variable.shape),
                "units": variable.attrs.get("units"),
                "long_name": variable.attrs.get("long_name"),
            }
            for name, variable in dataset.variables.items()
        }


def read_ceres_toa(
    path: str | Path,
    *,
    shortwave_variable: str,
    longwave_variable: str,
    time_variable: str = "time",
    latitude_variable: str = "lat",
    longitude_variable: str = "lon",
    selectors: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Read an explicit CF-netCDF CERES subset into a long-form TOA flux table.

    ``selectors`` are xarray ``isel`` indices applied before loading. Raw HDF4
    editions are not converted implicitly. Use provider-exported netCDF files.
    Invalid negative flux is marked missing, never clipped to valid zero flux.
    """
    xr = _xarray()
    with xr.open_dataset(path, decode_cf=True) as source:
        names = (
            time_variable,
            latitude_variable,
            longitude_variable,
            shortwave_variable,
            longwave_variable,
        )
        if any(name not in source.variables for name in names):
            raise ValueError(
                "Requested CERES variables are missing; inspect_environment_netcdf first"
            )
        subset = source[list(names)].isel(dict(selectors or {}))
        if not np.issubdtype(subset[time_variable].dtype, np.datetime64):
            raise ValueError("CERES time must be decoded from CF epoch metadata")
        for name in (shortwave_variable, longwave_variable):
            units = re.sub(r"[\s^*]", "", str(subset[name].attrs.get("units", ""))).lower()
            if units not in {"wm-2", "w/m2", "wm\u22122"}:
                raise ValueError(
                    f"Expected W m-2 for {name}, found {subset[name].attrs.get('units')}"
                )
        frame = subset.to_dataframe().reset_index(drop=False)
        frame = frame.loc[:, list(dict.fromkeys(names))].rename(
            columns={
                time_variable: "timestamp_utc",
                latitude_variable: "latitude_deg",
                longitude_variable: "longitude_deg",
                shortwave_variable: "toa_shortwave_w_m2",
                longwave_variable: "toa_longwave_w_m2",
            }
        )
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
    if frame["timestamp_utc"].isna().any():
        raise ValueError("CERES time coordinate contains missing timestamps")
    if (
        not np.isfinite(frame[["latitude_deg", "longitude_deg"]]).all().all()
        or (frame["latitude_deg"].abs() > 90).any()
        or ((frame["longitude_deg"] < -180) | (frame["longitude_deg"] > 360)).any()
    ):
        raise ValueError("CERES latitude/longitude coordinates must be geographic degrees")
    invalid_count = 0
    for name in ("toa_shortwave_w_m2", "toa_longwave_w_m2"):
        invalid = (frame[name] < 0) | ~np.isfinite(frame[name])
        invalid_count += int(invalid.sum())
        frame.loc[invalid, name] = np.nan
    frame.attrs.update(
        {
            "source": "NASA CERES",
            "source_file_sha256": _file_hash(Path(path)),
            "measurement_boundary": "top-of-atmosphere hemispheric flux",
            "source_variables": {"shortwave": shortwave_variable, "longwave": longwave_variable},
            "invalid_flux_values": invalid_count,
            "interpretation": "Requires Earth-view geometry; not irradiance at the spacecraft",
        }
    )
    return frame


def read_poes_metop(
    path: str | Path,
    *,
    channels: Sequence[str],
    time_variable: str = "time",
    quality_variables: Sequence[str] = (),
) -> pd.DataFrame:
    """Read chosen SEM-2 channels with their exact units and quality columns.

    Select detector-specific variables after inspecting the file. This function
    does not reinterpret counts as flux, integral channels as differential flux,
    or local flux as accumulated solar-cell damage. Supports CF time and NOAA's
    native daily format: independent same-length 1D variables and milliseconds
    since 1970 in the documented ``time.long_name`` (``units='time'``). The latter
    is recognized only with NOAA POES/MetOp provider metadata, not guessed for
    arbitrary numeric coordinates. Provider negative sentinel values are retained.
    """
    if not channels or len(set(channels)) != len(channels):
        raise ValueError("channels must be a nonempty sequence of unique provider variable names")
    xr = _xarray()
    with xr.open_dataset(path, decode_cf=True) as source:
        names = list(dict.fromkeys((time_variable, *channels, *quality_variables)))
        if any(name not in source.variables for name in names):
            raise ValueError("Requested SEM-2 variables are missing; inspect the file first")
        native_noaa = (
            source.attrs.get("Project") == "POES/MetOp"
            and source.attrs.get("naming_authority") == "gov.noaa.ngdc"
            and source[time_variable].attrs.get("long_name") == "milliseconds since 1970"
            and source[time_variable].attrs.get("units") == "time"
        )
        for name in names:
            if (
                source[name].ndim != 1
                or source[name].size != source[time_variable].size
                or (not native_noaa and source[name].dims != source[time_variable].dims)
            ):
                raise ValueError(
                    "Selected channels must share the one-dimensional record/time axis"
                )
        frame = pd.DataFrame({name: source[name].values for name in names})
        units = {name: source[name].attrs.get("units", "unspecified") for name in channels}
        descriptions = {name: source[name].attrs.get("long_name", name) for name in channels}
        global_attributes = {str(k): str(v) for k, v in source.attrs.items()}
    # CF metadata must have decoded time; numeric time without an epoch is ambiguous.
    if native_noaa:
        frame[time_variable] = pd.to_datetime(
            frame[time_variable], unit="ms", utc=True, errors="raise"
        ).dt.tz_localize(None)
    elif not np.issubdtype(frame[time_variable].dtype, np.datetime64):
        raise ValueError("SEM time was not decoded from CF epoch metadata")
    frame = frame.rename(columns={time_variable: "timestamp_utc"})
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    if frame["timestamp_utc"].isna().any():
        raise ValueError("SEM time contains missing timestamps")
    frame.attrs.update(
        {
            "source": "NOAA NCEI POES/MetOp SEM-2",
            "source_file_sha256": _file_hash(Path(path)),
            "units": units,
            "channel_descriptions": descriptions,
            "provider_attributes": global_attributes,
            "quality_variables": list(quality_variables),
            "time_encoding": "NOAA native milliseconds since 1970" if native_noaa else "CF epoch",
            "measurement_boundary": "local particle detector",
            "interpretation": "Channel response and contamination corrections require instrument-specific work",
        }
    )
    return frame
