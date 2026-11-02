"""Persistent GP snapshots with a cross-process download lock and circuit breaker."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class GPSnapshot:
    records: list[dict[str, Any]]
    source: str
    retrieved_at: datetime
    sha256: str
    cache_stale: bool = False
    warning: str | None = None


class GPUnavailableError(RuntimeError):
    """No usable snapshot is available; callers must not substitute demo data."""


class GPCache:
    """Cache provider queries for at least two hours, including across restarts.

    SQLite serializes downloads from processes sharing this local file. Any HTTP
    or malformed-response error pauses the entire provider until an operator
    calls :meth:`resume`. Existing snapshots remain available with an explicit
    warning; the orbit layer separately rejects old element epochs.

    Share one cache per deployment, on a local filesystem. Multiple hosts need
    a single ingestion service, not independent caches behind the same IP.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=35)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS snapshots "
            "(source TEXT, query TEXT, fetched REAL, digest TEXT, payload TEXT, "
            "PRIMARY KEY (source, query))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS paused (source TEXT PRIMARY KEY, reason TEXT)"
        )
        connection.commit()
        return connection

    def resume(self, source: str) -> None:
        """Resume downloads after a human investigates a provider failure."""
        connection = self._connect()
        try:
            with connection:
                connection.execute("DELETE FROM paused WHERE source = ?", (source,))
        finally:
            connection.close()

    def get(
        self,
        source: str,
        query: str,
        loader: Callable[[], list[dict[str, Any]]],
        *,
        now: datetime | None = None,
    ) -> GPSnapshot:
        use_wall_clock = now is None
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT fetched, digest, payload FROM snapshots WHERE source = ? AND query = ?",
                (source, query),
            ).fetchone()
            paused = connection.execute(
                "SELECT reason FROM paused WHERE source = ?", (source,)
            ).fetchone()
            if row and hashlib.sha256(row[2].encode()).hexdigest() != row[1]:
                raise GPUnavailableError("GP cache checksum mismatch; inspect the cache")
            age_s = max(0.0, now.timestamp() - row[0]) if row else float("inf")
            warning = paused[0] if paused else None
            if not paused and not 0 <= age_s < 7200:
                try:
                    records = loader()
                    if not isinstance(records, list) or any(
                        not isinstance(item, dict) for item in records
                    ):
                        raise ValueError("Invalid GP list")
                    payload = json.dumps(records, sort_keys=True, allow_nan=False)
                except (httpx.HTTPError, ValueError) as exc:
                    # Never persist request URLs/credentials or raw upstream bodies.
                    status = (
                        f"HTTP {exc.response.status_code}"
                        if isinstance(exc, httpx.HTTPStatusError)
                        else type(exc).__name__
                    )
                    warning = f"{source} downloads paused after {status}; operator review required"
                    connection.execute(
                        "INSERT OR REPLACE INTO paused VALUES (?, ?)", (source, warning)
                    )
                else:
                    received_at = datetime.now(UTC) if use_wall_clock else now
                    row = (
                        received_at.timestamp(),
                        hashlib.sha256(payload.encode()).hexdigest(),
                        payload,
                    )
                    age_s = 0
                    connection.execute(
                        "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?)",
                        (source, query, *row),
                    )
            connection.commit()
            if row is None:
                raise GPUnavailableError(warning or "No GP snapshot available")
            return GPSnapshot(
                records=json.loads(row[2]),
                source=source,
                retrieved_at=datetime.fromtimestamp(row[0], UTC),
                sha256=row[1],
                cache_stale=not 0 <= age_s < 7200,
                warning=warning,
            )
        finally:
            connection.close()
