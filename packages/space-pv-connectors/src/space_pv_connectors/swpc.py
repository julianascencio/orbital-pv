from __future__ import annotations

from typing import Any

from .http_base import HttpConnector


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
