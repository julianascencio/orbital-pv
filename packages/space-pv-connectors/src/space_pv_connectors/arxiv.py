"""Version-pinned arXiv metadata with original-byte provenance and offline cache."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

import httpx

from .http_base import DownloadReceipt
from .research_http import ResearchConnector, ResearchResponse

ATOM = "{http://www.w3.org/2005/Atom}"


def _paper_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}\.\d{4,5}v[1-9]\d*", value):
        raise ValueError("Use an explicit modern arXiv version, e.g. 2511.19468v2")
    return value


def parse_arxiv_atom(content: bytes, paper_id: str) -> dict[str, object]:
    """Parse one exact-version Atom entry; never silently substitute latest."""
    paper_id = _paper_id(paper_id)
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError("arXiv did not return valid Atom XML") from exc
    if root.tag != ATOM + "feed":
        raise ValueError("Expected an arXiv Atom feed")
    entries = root.findall(ATOM + "entry")
    if len(entries) != 1:
        raise LookupError("Expected exactly one arXiv entry")
    entry = entries[0]
    identifier = entry.findtext(ATOM + "id", "")
    if identifier not in (f"http://arxiv.org/abs/{paper_id}", f"https://arxiv.org/abs/{paper_id}"):
        raise ValueError("arXiv entry does not match the requested version")
    fields = {
        k: " ".join(entry.findtext(ATOM + k, "").split()) for k in ("title", "published", "updated")
    }
    authors = [a.findtext(ATOM + "name", "").strip() for a in entry.findall(ATOM + "author")]
    if not all(fields.values()) or not authors or not all(authors):
        raise ValueError("Incomplete arXiv metadata")
    return {
        "paper_id": paper_id,
        **fields,
        "authors": authors,
        "url": f"https://arxiv.org/abs/{paper_id}",
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
        "categories": [c.get("term", "") for c in entry.findall(ATOM + "category")],
        "evidence_kind": "bibliographic_metadata_not_validated_engineering_data",
    }


class ArxivConnector(ResearchConnector):
    """One explicit paper per request; reuse cache and observe arXiv rate limits.

    The original Atom bytes are cached with SHA-256, URL and retrieval time.
    This connector does not extract or promote scientific claims from PDFs.
    Downloading an accessible paper does not grant redistribution rights.
    """

    SOURCE = "arXiv"
    DOCUMENTATION = "https://info.arxiv.org/help/api/user-manual.html"
    BASE_URL = "https://export.arxiv.org/api/query"

    def paper(
        self, paper_id: str, *, cache_path: str | Path | None = None, refresh: bool = False
    ) -> ResearchResponse:
        """Fetch pinned metadata, or validate and read its existing local cache."""
        paper_id = _paper_id(paper_id)
        params = {"id_list": paper_id, "max_results": 1}
        request_url = str(httpx.URL(self.BASE_URL, params=params))
        path = Path(cache_path) if cache_path is not None else None
        sidecar = path.with_name(path.name + ".provenance.json") if path else None
        cached = path is not None and path.exists() and not refresh
        if cached:
            if sidecar is None or not sidecar.exists():
                raise ValueError("Cache has no provenance sidecar; use refresh=True")
            provenance = json.loads(sidecar.read_text(encoding="utf-8"))
            content = path.read_bytes()
            if (
                provenance.get("request_url") != request_url
                or provenance.get("source") != self.SOURCE
            ):
                raise ValueError("Cache belongs to a different request or provider")
            if provenance.get("sha256") != hashlib.sha256(content).hexdigest():
                raise ValueError("Cache checksum does not match its provenance")
            receipt = DownloadReceipt(
                **{k: provenance[k] for k in DownloadReceipt.__dataclass_fields__}
            )
        else:
            content_buffer = bytearray()
            with self._client.stream(
                "GET", self.BASE_URL, params=params, headers={"Accept": "application/atom+xml"}
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    if len(content_buffer) + len(chunk) > 2_000_000:
                        raise ValueError("arXiv metadata exceeds 2 MB")
                    content_buffer.extend(chunk)
                receipt = self.receipt(
                    self.SOURCE, str(response.url), bytes(content_buffer), path=path
                )
            content = bytes(content_buffer)
        data = parse_arxiv_atom(content, paper_id)
        if not cached and path is not None and sidecar is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            sidecar.write_text(
                json.dumps(
                    {
                        **asdict(receipt),
                        "request_url": request_url,
                        "documentation": self.DOCUMENTATION,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return ResearchResponse(data, receipt, request_url, self.DOCUMENTATION)

    def download_paper(
        self, paper_id: str, destination: str | Path, *, max_bytes: int = 20_000_000
    ) -> DownloadReceipt:
        """Download a selected version with a checksum receipt; no bulk crawl."""
        paper_id = _paper_id(paper_id)
        return self._download(
            f"https://arxiv.org/pdf/{paper_id}",
            destination,
            max_bytes=max_bytes,
            context={"paper_id": paper_id},
        )
