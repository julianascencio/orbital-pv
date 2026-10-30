from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

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
        if isinstance(norad_cat_id, bool) or not isinstance(norad_cat_id, int) or norad_cat_id < 1:
            raise ValueError("norad_cat_id must be a positive integer")
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

    def gp_history(
        self,
        norad_cat_id: int,
        *,
        start: str,
        end: str,
        cache_dir: str | Path,
        max_records: int = 100_000,
    ) -> list[dict[str, Any]]:
        """Fetch and cache a bounded, complete EPOCH interval in chronological order.

        Space-Track requests that GP history be downloaded once and reused from
        disk. A mandatory cache prevents repeated calls for an identical interval.
        ``start`` and ``end`` are inclusive, timezone-aware element epochs, not
        publication dates. Authentication is required for a cache miss. Queries
        over one year should use provider bulk/year files instead.

        Source: https://www.space-track.org/documentation
        """
        if isinstance(norad_cat_id, bool) or not isinstance(norad_cat_id, int) or norad_cat_id < 1:
            raise ValueError("norad_cat_id must be a positive integer")
        first, last = pd.Timestamp(start), pd.Timestamp(end)
        if pd.isna(first) or pd.isna(last) or first.tzinfo is None or last.tzinfo is None:
            raise ValueError("start and end require explicit timezones")
        first, last = first.tz_convert("UTC"), last.tz_convert("UTC")
        if first >= last or last - first > pd.Timedelta(days=366):
            raise ValueError("Use a positive interval of at most 366 days, or provider bulk files")
        if not 1 <= max_records <= 100_000:
            raise ValueError("max_records must be 1..100000")
        # Space-Track accepts epoch dates to seconds. Do not silently broaden a
        # subsecond request, which would invalidate alignment to telemetry.
        if first != first.floor("s") or last != last.floor("s"):
            raise ValueError("Space-Track history bounds must have whole-second precision")
        interval = f"{first.strftime('%Y-%m-%dT%H:%M:%S')}--{last.strftime('%Y-%m-%dT%H:%M:%S')}"
        url = (
            f"{self.BASE_URL}/basicspacedata/query/class/gp_history/norad_cat_id/{norad_cat_id}"
            f"/EPOCH/{interval}/orderby/EPOCH%20asc/limit/{max_records + 1}/format/json"
        )
        key = hashlib.sha256(url.encode()).hexdigest()
        directory = Path(cache_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"gp_history_{norad_cat_id}_{key[:20]}.json"
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            serialized = json.dumps(cached.get("records"), sort_keys=True, separators=(",", ":"))
            if (
                cached.get("url") != url
                or cached.get("sha256") != hashlib.sha256(serialized.encode()).hexdigest()
            ):
                raise ValueError("Space-Track history cache failed provenance verification")
            payload = cached["records"]
        else:
            response = self._client.get(url)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise ValueError("Unexpected Space-Track GP-history response")
        if len(payload) > max_records:
            raise ValueError("History exceeds max_records; narrow the interval to avoid truncation")
        for row in payload:
            if "EPOCH" not in row or str(row.get("NORAD_CAT_ID")) != str(norad_cat_id):
                raise ValueError("GP-history record lacks the requested satellite or EPOCH")
            epoch = pd.to_datetime(row["EPOCH"], utc=True, errors="raise")
            if pd.isna(epoch) or not first <= epoch <= last:
                raise ValueError("GP-history record falls outside the requested EPOCH interval")
        payload.sort(key=lambda row: pd.to_datetime(row["EPOCH"], utc=True))
        if not path.exists():
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            record = {
                "url": url,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
                "records": payload,
            }
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
        return payload
