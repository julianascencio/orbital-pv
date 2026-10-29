from __future__ import annotations

from typing import Any

from .http_base import HttpConnector


class CelesTrakConnector(HttpConnector):
    BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"

    def fetch_gp(
        self,
        *,
        catnr: int | None = None,
        intdes: str | None = None,
        group: str | None = None,
        name: str | None = None,
        output_format: str = "JSON",
    ) -> list[dict[str, Any]] | str:
        queries = {"CATNR": catnr, "INTDES": intdes, "GROUP": group, "NAME": name}
        selected = {key: value for key, value in queries.items() if value is not None}
        if len(selected) != 1:
            raise ValueError("Provide exactly one of catnr, intdes, group, or name")
        response = self._client.get(
            self.BASE_URL, params={**selected, "FORMAT": output_format.upper()}
        )
        response.raise_for_status()
        if output_format.upper().startswith("JSON"):
            payload = response.json()
            return [payload] if isinstance(payload, dict) else payload
        return response.text
