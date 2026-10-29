from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx


@dataclass(frozen=True, slots=True)
class DownloadReceipt:
    source: str
    url: str
    retrieved_at: str
    sha256: str
    bytes: int
    path: str | None = None


class HttpConnector:
    def __init__(self, *, timeout_s: float = 30.0, user_agent: str = "space-pv-analytics/0.2"):
        self._client = httpx.Client(timeout=timeout_s, follow_redirects=True, headers={"User-Agent": user_agent})

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def receipt(source: str, url: str, content: bytes, *, path: Path | None = None) -> DownloadReceipt:
        return DownloadReceipt(source, url, datetime.now(UTC).isoformat(), sha256(content).hexdigest(), len(content), str(path) if path else None)
