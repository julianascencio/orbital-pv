"""Original ALISIO-1 / DRAGO-2 first-observation images published by IACTEC-Espacio."""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar
from urllib.parse import urlencode

from .http_base import DownloadReceipt
from .research_http import ResearchConnector

_SHARE = "https://cloud.iac.es/index.php/s/RS9pKNp272N5LEL"
_FOLDER = "/Primeras imágenes ALISIO-1 (Feb. 2024)/Imágenes"


@dataclass(frozen=True, slots=True)
class AlisioScene:
    """One original false-colour media product from the February 2024 release."""

    title: str
    filename: str
    sha256: str
    bundled: bool = False

    @property
    def url(self) -> str:
        """Public download URL for this file in the IAC share."""
        return f"{_SHARE}/download?{urlencode({'path': _FOLDER, 'files': self.filename})}"


class AlisioConnector(ResearchConnector):
    """Access five curated first-observation composites and two offline originals.

    Use the keys in ``scenes`` to select a product. The release date is the
    publication date. The composites contain display colours; the PNG/JPEG
    channels do not supply calibrated spectral or electrical measurements.
    """

    SOURCE = "ALISIO-1 / DRAGO-2"
    DOCUMENTATION = "https://www.iac.es/en/outreach/news/first-observations-canary-islands-satellite-alisio-1-space"
    CREDIT = "IACTEC-Espacio, Instituto de Astrofísica de Canarias (IAC)"
    USAGE_TERMS = "https://www.iac.es/en/outreach/multimedia-gallery"
    #: IAC instrument-sheet upper bound while budgeting the camera load (watts).
    #: https://www.iac.es/system/files/documents/2023-09/ALISIO.pdf
    DRAGO2_POWER_CEILING_W = 5.5

    scenes: ClassVar[Mapping[str, AlisioScene]] = MappingProxyType(
        {
            "la-palma": AlisioScene(
                "La Palma",
                "la_palma.png",
                "8e39a7d6121948b531cfccfd30700c4a72d1f82025969a1675a10698cc0998c2",
                bundled=True,
            ),
            "el-hierro": AlisioScene(
                "El Hierro",
                "el_hierro.png",
                "518eeb7fa409756a0d427959783408e93090aa4af8582c0a834cd5d00b2be1ae",
                bundled=True,
            ),
            "chihuahua": AlisioScene(
                "Chihuahua",
                "DRAGO_LR.jpg",
                "0972ce0d5a5d9ec10532d16b3fc4b4381e82a3da14fc9dde6de3fa0312fc998c",
            ),
            "guadiana": AlisioScene(
                "Guadiana estuary",
                "drago_lr-2.jpg",
                "038264597d8384ac1c0ac1cb7e318715f3e07ca41d49d46d0fbc950319351edd",
            ),
            "donana": AlisioScene(
                "Doñana",
                "donana_crop.jpg",
                "c9b728d8410e8068cbc283aa9147c90db98dfdab69129325be522adb047e1e59",
            ),
        }
    )

    @classmethod
    def bundled_image(cls, scene_id: str) -> bytes:
        """Read and verify an original island PNG without a network connection."""
        scene = cls.scenes[scene_id]
        if not scene.bundled:
            raise ValueError(f"Use download() for {scene.title}; this image is available online")
        content = (
            files("space_pv_connectors").joinpath("_data", "alisio", scene.filename).read_bytes()
        )
        if sha256(content).hexdigest() != scene.sha256:
            raise ValueError(f"Packaged image checksum mismatch for {scene.title}")
        return content

    def download(self, scene_id: str, destination: str | Path) -> DownloadReceipt:
        """Fetch an original to a file and write a checksum and attribution sidecar."""
        scene = self.scenes[scene_id]
        return self._download(
            scene.url,
            destination,
            checksum=f"sha256:{scene.sha256}",
            max_bytes=4_000_000,
            context={
                "scene": scene.title,
                "original_filename": scene.filename,
                "credit": self.CREDIT,
                "usage_terms": self.USAGE_TERMS,
                "share": _SHARE,
            },
        )
