"""Measured total and spectral solar irradiance from LASP LISIRD.

These calibrated Level-3 science products measure incoming sunlight; they
are not solar-array electrical-output telemetry. Source:
https://lasp.colorado.edu/lisird/ and https://lasp.colorado.edu/tsis/data/.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote

import numpy as np
import pandas as pd

from .http_base import HttpConnector


def _utc_bound(value: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if not isinstance(timestamp, pd.Timestamp):
        raise ValueError("LISIRD time bounds must be valid dates")
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def _decode_time(values: pd.Series, units: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if units == "Julian Date":
        # Subtract the Unix epoch before conversion so missing/invalid Julian
        # dates are safely handled by errors='coerce'.
        return pd.to_datetime(
            numeric - 2440587.5, unit="D", origin="unix", utc=True, errors="coerce"
        )
    supported = {
        "milliseconds since 1970-01-01": "ms",
        "seconds since 1970-01-01": "s",
    }
    if units not in supported:
        raise ValueError(f"Unsupported LISIRD time units: {units!r}")
    return pd.to_datetime(numeric, unit=supported[units], utc=True, errors="coerce")


class LisirdConnector(HttpConnector):
    """Retrieve bounded, measured TSIS-1/SORCE irradiance datasets.

    The LaTiS ``jsond`` response carries parameter order and units. Cache files
    contain the original JSON bytes plus a ``.meta.json`` sidecar binding the
    response to its dataset, time range and SHA-256. Reusing a different query
    with the same cache path raises an error instead of returning stale data.
    Data access is public; retain LASP/instrument-team attribution and consult
    the product release notes for the version used.
    """

    API = "https://lasp.colorado.edu/lisird/latis/dap"
    TSI_DATASETS: ClassVar[frozenset[str]] = frozenset(
        {"tsis_tsi_24hr", "tsis_tsi_6hr", "sorce_tsi_24hr_l3", "sorce_tsi_6hr_l3"}
    )
    SSI_DATASETS: ClassVar[frozenset[str]] = frozenset({"tsis_ssi_24hr", "tsis_ssi_12hr"})

    def _frame(
        self,
        dataset_id: str,
        *,
        time_min: str,
        time_max: str,
        cache_path: str | Path | None,
        required: dict[str, str],
    ) -> pd.DataFrame:
        start, stop = _utc_bound(time_min), _utc_bound(time_max)
        if stop <= start:
            raise ValueError("time_max must be later than time_min (the end bound is exclusive)")
        query = {
            "dataset_id": dataset_id,
            "time_min": start.isoformat(),
            "time_max": stop.isoformat(),
            "format": "jsond",
        }
        url = (
            f"{self.API}/{dataset_id}.jsond?"
            f"time%3E={quote(start.isoformat().replace('+00:00', 'Z'), safe='')}"
            f"&time%3C{quote(stop.isoformat().replace('+00:00', 'Z'), safe='')}"
        )
        path = Path(cache_path) if cache_path is not None else None
        sidecar = path.with_suffix(path.suffix + ".meta.json") if path is not None else None
        cached = path is not None and path.exists()
        if cached:
            if sidecar is None or not sidecar.exists():
                raise ValueError(
                    "LISIRD cache has no provenance sidecar; delete it or choose a new cache path"
                )
            provenance = json.loads(sidecar.read_text(encoding="utf-8"))
            content = path.read_bytes()
            if provenance.get("request") != query:
                raise ValueError(
                    "LISIRD cache belongs to a different query; choose a new cache path"
                )
            if provenance.get("sha256") != sha256(content).hexdigest():
                raise ValueError("LISIRD cache SHA-256 does not match its provenance sidecar")
        else:
            response = self._client.get(url)
            response.raise_for_status()
            content = response.content
            provenance = {
                **asdict(self.receipt("LASP LISIRD", str(response.url), content, path=path)),
                "request": query,
                "documentation": f"https://lasp.colorado.edu/lisird/data/{dataset_id}/",
            }

        try:
            document = json.loads(content)[dataset_id]
            parameters = document["parameters"]
            metadata = document["metadata"]
            data = document["data"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid LISIRD jsond response for {dataset_id}") from exc
        if (
            not isinstance(parameters, list)
            or not all(isinstance(name, str) for name in parameters)
            or len(parameters) != len(set(parameters))
            or not isinstance(metadata, dict)
            or not isinstance(data, list)
            or any(not isinstance(row, list) or len(row) != len(parameters) for row in data)
        ):
            raise ValueError(f"Invalid LISIRD table structure for {dataset_id}")
        if "time" not in parameters:
            raise ValueError("LISIRD response has no nominal time coordinate")
        for field, units in required.items():
            if field not in parameters or metadata.get(field, {}).get("units") != units:
                raise ValueError(f"LISIRD field {field!r} must be present with units {units!r}")

        frame = pd.DataFrame(data, columns=parameters)
        for column in parameters:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame[column] = frame[column].where(np.isfinite(frame[column]))
            fill = metadata.get(column, {}).get("missing_value")
            if fill is not None:
                try:
                    fill_value = float(fill)
                except (ValueError, TypeError):
                    continue
                frame[column] = frame[column].mask(frame[column].eq(fill_value))
        time_units = metadata.get("time", {}).get("units", "")
        frame["timestamp"] = _decode_time(frame["time"], time_units)
        frame = frame[frame["timestamp"].ge(start) & frame["timestamp"].lt(stop)].copy()
        if "avg_measurement_date" in frame:
            frame["average_measurement_timestamp"] = _decode_time(
                frame["avg_measurement_date"],
                metadata.get("avg_measurement_date", {}).get("units", ""),
            )
        frame["dataset_id"] = dataset_id
        frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
        frame.attrs.update(
            {
                "provenance": provenance,
                "source_metadata": metadata,
                "source_units": {name: info.get("units") for name, info in metadata.items()},
                "timestamp_basis": "nominal center of the Level-3 averaging interval",
            }
        )
        # Save only a successfully decoded, unit-checked source response.
        if not cached and path is not None and sidecar is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            sidecar.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        return frame

    def total_solar_irradiance(
        self,
        dataset_id: str = "tsis_tsi_24hr",
        *,
        time_min: str,
        time_max: str,
        cache_path: str | Path | None = None,
    ) -> pd.DataFrame:
        """Return measured daily or six-hourly TSI in W/m².

        The interval is ``[time_min, time_max)`` in UTC, applied to the nominal
        averaging-bin timestamp. At-1-AU and actual-Earth-distance irradiances
        remain separate. Source zero fill values become NaN; missing intervals
        are not interpolated. ``valid_measurement`` requires both irradiances
        to be finite and positive. ``provisional_flag`` is preserved when
        present and is not interpreted as a missing-value flag.
        """
        if dataset_id not in self.TSI_DATASETS:
            raise ValueError(f"Choose a measured TSI dataset from {sorted(self.TSI_DATASETS)}")
        frame = self._frame(
            dataset_id,
            time_min=time_min,
            time_max=time_max,
            cache_path=cache_path,
            required={
                "tsi_1au": "W/m^2",
                "tsi_true_earth": "W/m^2",
                "measurement_uncertainty_1au": "W/m^2",
                "measurement_uncertainty_true_earth": "W/m^2",
            },
        )
        aliases = {
            "tsi_1au": "tsi_1au_w_m2",
            "tsi_true_earth": "tsi_earth_w_m2",
            "measurement_uncertainty_1au": "uncertainty_1au_w_m2",
            "measurement_uncertainty_true_earth": "uncertainty_earth_w_m2",
        }
        for source, canonical in aliases.items():
            if source in frame:
                frame[canonical] = frame[source]
        frame["valid_measurement"] = frame["tsi_1au_w_m2"].gt(0) & frame["tsi_earth_w_m2"].gt(0)
        return frame

    def spectral_irradiance(
        self,
        dataset_id: str = "tsis_ssi_24hr",
        *,
        time_min: str,
        time_max: str,
        cache_path: str | Path | None = None,
    ) -> pd.DataFrame:
        """Return measured TSIS-1 SIM spectra as wavelength-resolved rows.

        Wavelength is in nm, irradiance in W/m²/nm, and the time interval is
        end-exclusive. All source quality bits are retained as ``quality_flag``;
        ``quality_good`` conservatively selects zero-flag bins. Flagged bins
        remain in the frame. Do not integrate across missing or rejected
        spectral intervals or assume this 200--2400 nm product covers all TSI.
        At most 31 days may be requested per call to bound response size.
        """
        if dataset_id not in self.SSI_DATASETS:
            raise ValueError(f"Choose a measured SSI dataset from {sorted(self.SSI_DATASETS)}")
        if _utc_bound(time_max) - _utc_bound(time_min) > pd.Timedelta(days=31):
            raise ValueError("Request no more than 31 days of spectral irradiance per call")
        frame = self._frame(
            dataset_id,
            time_min=time_min,
            time_max=time_max,
            cache_path=cache_path,
            required={
                "wavelength": "nm",
                "irradiance_1au": "W/m^2/nm",
                "irradiance_true_earth": "W/m^2/nm",
                "quality": "Bit Flag",
            },
        )
        frame["wavelength_nm"] = frame["wavelength"]
        frame["irradiance_1au_w_m2_nm"] = frame["irradiance_1au"]
        frame["irradiance_earth_w_m2_nm"] = frame["irradiance_true_earth"]
        frame["quality_flag"] = frame["quality"]
        frame["quality_good"] = frame["quality_flag"].eq(0)
        frame["valid_measurement"] = (
            frame["wavelength_nm"].gt(0)
            & frame["irradiance_1au_w_m2_nm"].ge(0)
            & frame["irradiance_earth_w_m2_nm"].ge(0)
        )
        return frame.sort_values(["timestamp", "wavelength_nm"]).reset_index(drop=True)


__all__ = ["LisirdConnector"]
