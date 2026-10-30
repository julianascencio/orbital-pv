from __future__ import annotations

import json
import re
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .http_base import HttpConnector


def _normalize_goes_particle_flux(payload: object, particle: str) -> pd.DataFrame:
    if particle not in {"protons", "electrons"}:
        raise ValueError("particle must be 'protons' or 'electrons'")
    if not isinstance(payload, list) or not payload:
        raise ValueError("GOES particle feed must be a nonempty list of measurement records")
    frame = pd.DataFrame(payload)
    required = {"time_tag", "satellite", "energy", "flux"}
    if missing := required - set(frame.columns):
        raise ValueError(f"Missing GOES particle fields: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["time_tag"], utc=True, errors="coerce")
    if frame["timestamp"].isna().any():
        raise ValueError("GOES particle feed contains invalid timestamps")
    satellite_numbers = pd.to_numeric(frame["satellite"], errors="coerce")
    if (satellite_numbers.isna() | (satellite_numbers <= 0) | (satellite_numbers % 1 != 0)).any():
        raise ValueError("GOES particle feed contains invalid satellite identifiers")
    frame["satellite_id"] = "GOES-" + satellite_numbers.astype(int).astype(str)
    thresholds = (
        frame["energy"].astype(str).str.extract(r"^>=?\s*(\d+(?:\.\d+)?)\s+MeV$", expand=False)
    )
    if thresholds.isna().any():
        raise ValueError("GOES integral energy labels must specify a threshold in MeV")
    frame["energy_threshold_mev"] = pd.to_numeric(thresholds)
    flux = pd.to_numeric(frame["flux"], errors="coerce")
    frame["is_valid_flux"] = np.isfinite(flux) & (flux >= 0)
    frame["flux_cm2_s_sr"] = flux.where(frame["is_valid_flux"])
    frame["particle"] = particle
    frame["flux_unit"] = f"{particle} cm^-2 s^-1 sr^-1"
    frame = frame.sort_values(["satellite_id", "energy_threshold_mev", "timestamp"]).reset_index(
        drop=True
    )
    frame.attrs.update(
        source="NOAA SWPC GOES integral particle measurements",
        units={"flux_cm2_s_sr": f"{particle} cm^-2 s^-1 sr^-1", "energy_threshold_mev": "MeV"},
        invalid_flux_rows=int((~frame["is_valid_flux"]).sum()),
        interpretation="Geostationary environment measurements; not a spacecraft-specific radiation dose.",
    )
    return frame


def load_goes_integral_particle_flux(path: str | Path, *, particle: str) -> pd.DataFrame:
    """Read an original SWPC integral-flux JSON snapshot without network access.

    Raw fields are retained. Negative, nonfinite or missing flux values become
    NaN in ``flux_cm2_s_sr`` and are flagged by ``is_valid_flux``. Integral energy
    channels overlap and must not be added together. Satellite identity is taken
    from every measurement, since primary proton/electron sources can differ.
    """
    content = Path(path).read_bytes()
    frame = _normalize_goes_particle_flux(json.loads(content), particle)
    frame.attrs["sha256"] = sha256(content).hexdigest()
    frame.attrs["source_file"] = str(path)
    return frame


class NoaaSwpcConnector(HttpConnector):
    """NOAA Space Weather Prediction Center JSON feed connector."""

    BASE_URL = "https://services.swpc.noaa.gov"

    def fetch_json(self, relative_path: str) -> Any:
        path = relative_path.lstrip("/")
        if ".." in path:
            raise ValueError("Path traversal is not allowed")
        response = self._client.get(f"{self.BASE_URL}/{path}")
        response.raise_for_status()
        return response.json()

    def planetary_k_index(self) -> Any:
        return self.fetch_json("products/noaa-planetary-k-index.json")

    def f107_flux(self) -> Any:
        return self.fetch_json("json/f107_cm_flux.json")

    def real_time_solar_wind(self) -> Any:
        return self.fetch_json("json/rtsw/rtsw_wind_1m.json")

    def goes_integral_particle_flux(
        self,
        particle: str,
        *,
        role: str = "primary",
        period: str = "7-day",
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Fetch measured GOES integral proton or electron flux.

        ``period`` selects a rolling ``6-hour``, ``1-day``, ``3-day`` or ``7-day``
        observation feed. This is not a historical-date API. ``role`` is primary
        or secondary; the actual GOES number is retained for each record.

        A cache stores the original response with a JSON provenance sidecar.
        Subsequent calls reuse that exact snapshot unless ``refresh=True``.
        A mismatched request or checksum raises instead of silently using data
        for another channel. Electron flux can be contaminated during energetic
        proton events; this feed does not supply a per-record contamination flag.
        """
        if particle not in {"protons", "electrons"}:
            raise ValueError("particle must be 'protons' or 'electrons'")
        if role not in {"primary", "secondary"}:
            raise ValueError("role must be 'primary' or 'secondary'")
        if not re.fullmatch(r"(?:6-hour|1-day|3-day|7-day)", period):
            raise ValueError("period must be '6-hour', '1-day', '3-day' or '7-day'")
        url = f"{self.BASE_URL}/json/goes/{role}/integral-{particle}-{period}.json"
        path = Path(cache_path) if cache_path is not None else None
        sidecar = path.with_suffix(path.suffix + ".metadata.json") if path is not None else None
        if path is not None and path.exists() and not refresh:
            if sidecar is None or not sidecar.exists():
                raise ValueError(
                    "GOES cache provenance is missing; use refresh=True to retrieve it again"
                )
            metadata = json.loads(sidecar.read_text())
            content = path.read_bytes()
            if metadata.get("url") != url or metadata.get("sha256") != sha256(content).hexdigest():
                raise ValueError("GOES cache request or checksum mismatch; use refresh=True")
        else:
            response = self._client.get(url)
            response.raise_for_status()
            content = response.content
            # Validate before persisting so an upstream error cannot poison the cache.
            _normalize_goes_particle_flux(json.loads(content), particle)
            metadata = asdict(self.receipt("NOAA SWPC GOES", url, content, path=path))
            metadata.update(particle=particle, role=role, period=period)
            if path is not None and sidecar is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
        frame = _normalize_goes_particle_flux(json.loads(content), particle)
        frame.attrs.update(metadata)
        return frame


__all__ = ["NoaaSwpcConnector", "load_goes_integral_particle_flux"]
