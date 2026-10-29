from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from .http_base import DownloadReceipt, HttpConnector


class NaifKernelConnector(HttpConnector):
    """Download explicitly selected NASA NAIF SPICE kernels with provenance receipt."""

    ALLOWED_HOST = "naif.jpl.nasa.gov"

    def download(self, url: str, destination: str | Path) -> DownloadReceipt:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != self.ALLOWED_HOST:
            raise ValueError("NAIF connector accepts only https://naif.jpl.nasa.gov URLs")
        response = self._client.get(url)
        response.raise_for_status()
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return self.receipt("NASA NAIF", url, response.content, path=path)
