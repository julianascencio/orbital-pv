from __future__ import annotations

from typing import Any

from .http_base import HttpConnector


class SpaceTrackConnector(HttpConnector):
    """Authenticated Space-Track GP/GP-history connector.

    Credentials should be supplied by environment/secrets management, never committed.
    """

    BASE_URL = "https://www.space-track.org"

    def login(self, identity: str, password: str) -> None:
        response = self._client.post(
            f"{self.BASE_URL}/ajaxauth/login",
            data={"identity": identity, "password": password},
        )
        response.raise_for_status()
        if "login" in str(response.url).lower() and response.status_code == 200:
            text = response.text.lower()
            if "password" in text and "identity" in text:
                raise PermissionError("Space-Track authentication did not establish a session")

    def latest_gp(self, norad_cat_id: int) -> list[dict[str, Any]]:
        url = (
            f"{self.BASE_URL}/basicspacedata/query/class/gp/"
            f"norad_cat_id/{norad_cat_id}/orderby/EPOCH%20desc/limit/1/format/json"
        )
        response = self._client.get(url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected Space-Track GP response")
        return payload
