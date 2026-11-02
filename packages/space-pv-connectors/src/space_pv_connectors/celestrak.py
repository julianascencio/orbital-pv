from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .gp_cache import GPCache, GPSnapshot
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
            self.BASE_URL,
            params={**selected, "FORMAT": output_format.upper()},
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise httpx.HTTPStatusError(
                "CelesTrak requires HTTP 200; stop and investigate",
                request=response.request,
                response=response,
            )
        if output_format.upper().startswith("JSON"):
            payload = response.json()
            return [payload] if isinstance(payload, dict) else payload
        return response.text

    def fetch_gp_cached(
        self, cache_path: str | Path, *, catnr: int | None = None, group: str | None = None
    ) -> GPSnapshot:
        """Fetch OMM JSON with a persistent two-hour minimum refresh interval.

        Empty results are cached too. Never delete the cache to force refreshes.
        See https://celestrak.org/usage-policy.php.
        """
        if (catnr is None) == (group is None):
            raise ValueError("Provide exactly one of catnr or group")
        if catnr is not None and (
            isinstance(catnr, bool) or not isinstance(catnr, int) or not 1 <= catnr <= 999999999
        ):
            raise ValueError("catnr must be an integer in 1..999999999")
        if group is not None:
            group = group.strip().lower()
            if not group or not all(c.isascii() and (c.isalnum() or c == "-") for c in group):
                raise ValueError("Invalid CelesTrak group")

        def load() -> list[dict[str, Any]]:
            records = self.fetch_gp(catnr=catnr, group=group, output_format="JSON")
            if not isinstance(records, list):
                raise ValueError("Expected GP JSON records")
            return records

        query = f"CATNR={catnr}" if catnr is not None else f"GROUP={group}"
        return GPCache(cache_path).get("CelesTrak", query, load)
