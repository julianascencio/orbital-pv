"""Provenance and bounded downloads shared by the research API connectors."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from .http_base import DownloadReceipt, HttpConnector


@dataclass(frozen=True, slots=True)
class ResearchResponse:
    """Provider metadata and the receipt for its original response bytes.

    ``request_url`` includes non-secret query parameters; authentication headers
    are never serialized. JSON connectors retain provider units, licenses,
    pagination, versions and uncertainty fields. The arXiv connector documents
    its Atom-to-metadata normalization and can cache original XML bytes.
    Neither representation is a validated engineering or PV specification.
    """

    data: Any
    receipt: DownloadReceipt
    request_url: str
    documentation: str


def bounded_int(value: int, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer between {lower} and {upper}")
    return value


def required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def require_fields(data: Any, /, **fields: type) -> None:
    if not isinstance(data, dict) or any(
        not isinstance(data.get(key), kind) for key, kind in fields.items()
    ):
        raise ValueError(f"Unexpected provider response; required fields: {', '.join(fields)}")


def _validate_json(data: Any) -> None:
    if isinstance(data, dict) and (
        data.get("error") or data.get("errors") or data.get("status") == "ERROR"
    ):
        raise ValueError("Provider returned an API error in its JSON response")


class ResearchConnector(HttpConnector):
    """Internal HTTP helpers; no automatic crawling, retries or paid requests."""

    SOURCE = "Research API"
    DOCUMENTATION = ""

    def _json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_path: str | Path | None = None,
        refresh: bool = False,
        validate: Callable[[Any], None] = _validate_json,
    ) -> ResearchResponse:
        request_url = str(httpx.URL(url, params=params))
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
                **{key: provenance[key] for key in DownloadReceipt.__dataclass_fields__}
            )
        else:
            response = self._client.get(
                url, params=params, headers={"Accept": "application/json", **(headers or {})}
            )
            response.raise_for_status()
            content = response.content
            receipt = self.receipt(self.SOURCE, str(response.url), content, path=path)
        try:
            data = json.loads(content)
        except ValueError as exc:
            raise ValueError(f"{self.SOURCE} did not return valid JSON") from exc
        _validate_json(data)
        validate(data)
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

    def _download(
        self,
        url: str,
        destination: str | Path,
        *,
        checksum: str | None = None,
        max_bytes: int = 100_000_000,
        context: dict[str, Any] | None = None,
    ) -> DownloadReceipt:
        """Download public bytes; verify optional ``algorithm:hex`` checksum.

        Nothing is written until the size and checksum checks pass. Downloads
        deliberately use no API credentials, including across redirects.
        """
        bounded_int(max_bytes, "max_bytes", 1, 2**40)
        parsed = httpx.URL(url)
        if parsed.scheme != "https" or not parsed.host or parsed.userinfo:
            raise ValueError("Downloads require a public HTTPS URL without credentials")
        expected = None
        digest = None
        if checksum is not None:
            algorithm, sep, expected = checksum.lower().partition(":")
            algorithm = algorithm.replace("-", "")
            if not sep or algorithm not in {"md5", "sha1", "sha256", "sha512"}:
                raise ValueError("Unsupported provider checksum")
            digest = hashlib.new(algorithm, usedforsecurity=False)
            if len(expected) != digest.digest_size * 2 or any(
                c not in "0123456789abcdef" for c in expected
            ):
                raise ValueError("Invalid provider checksum")
        content = bytearray()
        with self._client.stream("GET", url) as response:
            response.raise_for_status()
            if "text/html" in response.headers.get("content-type", "").lower():
                raise ValueError("Download returned an HTML page instead of a data file")
            for chunk in response.iter_bytes():
                if len(content) + len(chunk) > max_bytes:
                    raise ValueError(
                        "Download exceeds max_bytes; inspect metadata before increasing it"
                    )
                content.extend(chunk)
                if digest is not None:
                    digest.update(chunk)
            final_url = str(response.url)
        if digest is not None and digest.hexdigest() != expected:
            raise ValueError("Download checksum does not match provider metadata")
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        receipt = self.receipt(self.SOURCE, final_url, bytes(content), path=path)
        path.with_name(path.name + ".provenance.json").write_text(
            json.dumps(
                {
                    **asdict(receipt),
                    "request_url": url,
                    "documentation": self.DOCUMENTATION,
                    "provider_checksum": checksum,
                    "context": context or {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return receipt


__all__ = ["ResearchResponse"]
