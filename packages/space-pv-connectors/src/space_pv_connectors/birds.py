from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from .http_base import DownloadReceipt, HttpConnector


class BirdsEPSConnector(HttpConnector):
    API = "https://api.github.com/repos/BIRDSOpenSource/EPS_dataset/contents"
    SATELLITES: ClassVar[frozenset[str]] = frozenset({"NEPALISAT", "RAAVANA", "TSURU", "UGUISU"})

    def download(self, satellite: str, destination: str | Path) -> DownloadReceipt:
        name = satellite.upper()
        if name not in self.SATELLITES:
            raise ValueError(
                f"Unknown BIRDS EPS satellite: {satellite}; choose {sorted(self.SATELLITES)}"
            )
        metadata = self._client.get(f"{self.API}/{name}.xlsx")
        metadata.raise_for_status()
        download_url = metadata.json()["download_url"]
        response = self._client.get(download_url)
        response.raise_for_status()
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return self.receipt("BIRDS EPS", download_url, response.content, path=path)
