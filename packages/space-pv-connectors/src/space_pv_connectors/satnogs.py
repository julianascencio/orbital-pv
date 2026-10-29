from __future__ import annotations

from typing import Any

from .http_base import HttpConnector


class SatnogsDbConnector(HttpConnector):
    """Public SatNOGS DB API for satellite metadata, TLEs and decoded telemetry."""

    BASE_URL = "https://db.satnogs.org/api"

    def satellite(self, sat_id: str) -> dict[str, Any]:
        response = self._client.get(f"{self.BASE_URL}/satellites/{sat_id}/")
        response.raise_for_status()
        return response.json()

    def satellites(self, **filters: str | int | float | bool) -> dict[str, Any] | list[dict[str, Any]]:
        response = self._client.get(f"{self.BASE_URL}/satellites/", params=filters)
        response.raise_for_status()
        return response.json()

    def telemetry(self, **filters: str | int | float | bool) -> dict[str, Any] | list[dict[str, Any]]:
        """Retrieve decoded/raw telemetry records using SatNOGS API filter parameters."""
        response = self._client.get(f"{self.BASE_URL}/telemetry/", params=filters)
        response.raise_for_status()
        return response.json()

    def tle(self, **filters: str | int | float | bool) -> dict[str, Any] | list[dict[str, Any]]:
        response = self._client.get(f"{self.BASE_URL}/tle/", params=filters)
        response.raise_for_status()
        return response.json()

    def historical_tle(self, **filters: str | int | float | bool) -> dict[str, Any] | list[dict[str, Any]]:
        response = self._client.get(f"{self.BASE_URL}/tle/historical/", params=filters)
        response.raise_for_status()
        return response.json()
