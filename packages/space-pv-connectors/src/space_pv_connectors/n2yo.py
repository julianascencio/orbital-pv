"""Optional server-side N2YO calculated-position connector."""

from __future__ import annotations

import math
import os
from typing import Any
from urllib.parse import quote

import httpx

from .http_base import HttpConnector


class N2YOConnector(HttpConnector):
    """N2YO REST v1. Keep API keys on the server, outside browser bundles.

    Positions are provider predictions, not satellite GPS telemetry. The free
    service documents 1,000 position calls/hour and at most 300 samples/call.
    No retries are made here. Bulk tracking should use cached GP + local SGP4.
    https://www.n2yo.com/api/
    """

    def __init__(self, *, api_key: str | None = None, timeout_s: float = 30):
        key = api_key or os.environ.get("N2YO_API_KEY")
        if not key or not key.strip():
            raise ValueError("Set N2YO_API_KEY or provide api_key")
        super().__init__(timeout_s=timeout_s)
        self._api_key = key

    def positions(
        self,
        norad_id: int,
        *,
        observer_lat: float,
        observer_lon: float,
        observer_alt_m: float = 0,
        seconds: int = 60,
    ) -> dict[str, Any]:
        """Return the provider's timestamped position JSON, including provenance.

        ``sataltitude`` in the provider payload is km; observer altitude is m.
        Element epoch is not supplied by this endpoint and remains unknown.
        """
        if (
            isinstance(norad_id, bool)
            or not isinstance(norad_id, int)
            or not 1 <= norad_id <= 999999999
        ):
            raise ValueError("norad_id must be an integer in 1..999999999")
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 300:
            raise ValueError("seconds must be an integer in 1..300")
        if not all(math.isfinite(v) for v in (observer_lat, observer_lon, observer_alt_m)):
            raise ValueError("Observer coordinates must be finite")
        if not -90 <= observer_lat <= 90 or not -180 <= observer_lon <= 180:
            raise ValueError("Invalid observer latitude/longitude")
        url = (
            f"https://api.n2yo.com/rest/v1/satellite/positions/{norad_id}/"
            f"{observer_lat}/{observer_lon}/{observer_alt_m}/{seconds}/"
        )
        try:
            response = self._client.get(
                f"{url}&apiKey={quote(self._api_key, safe='')}", follow_redirects=False
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            # HTTPX errors can include URLs containing the API key.
            raise RuntimeError(
                "N2YO request failed; check service status and credentials"
            ) from None
        if (
            not isinstance(payload, dict)
            or payload.get("error")
            or not isinstance(payload.get("positions"), list)
            or str(payload.get("info", {}).get("satid")) != str(norad_id)
        ):
            raise ValueError("N2YO returned no valid positions for the requested satellite")
        return {
            **payload,
            "source": "N2YO",
            "position_kind": "predicted",
            "element_epoch": None,
            "sataltitude_unit": "km",
        }
