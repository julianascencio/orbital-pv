from __future__ import annotations

from typing import Any

from .http_base import HttpConnector


class SscWebConnector(HttpConnector):
    """NASA Satellite Situation Center metadata and ephemeris-service connector."""

    BASE_URL = "https://sscweb.gsfc.nasa.gov/WS/sscr/2"

    def observatories(self) -> str:
        response = self._client.get(f"{self.BASE_URL}/observatories", headers={"Accept": "application/xml"})
        response.raise_for_status()
        return response.text

    def locations(self, request_payload: dict[str, Any]) -> Any:
        response = self._client.post(
            f"{self.BASE_URL}/locations",
            json=request_payload,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()
