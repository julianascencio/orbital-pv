from __future__ import annotations

from typing import Any

from .http_base import HttpConnector


class CdawebHapiConnector(HttpConnector):
    BASE_URL = "https://cdaweb.gsfc.nasa.gov/hapi"

    def catalog(self) -> dict[str, Any]:
        response = self._client.get(f"{self.BASE_URL}/catalog")
        response.raise_for_status()
        return response.json()

    def info(self, dataset_id: str) -> dict[str, Any]:
        response = self._client.get(f"{self.BASE_URL}/info", params={"id": dataset_id})
        response.raise_for_status()
        return response.json()

    def data(
        self, dataset_id: str, *, time_min: str, time_max: str, parameters: list[str] | None = None
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "id": dataset_id,
            "time.min": time_min,
            "time.max": time_max,
            "format": "json",
        }
        if parameters:
            params["parameters"] = ",".join(parameters)
        response = self._client.get(f"{self.BASE_URL}/data", params=params)
        response.raise_for_status()
        return response.json()
