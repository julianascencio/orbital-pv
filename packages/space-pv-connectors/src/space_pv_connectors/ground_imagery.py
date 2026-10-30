"""Ground imagery from the public Earth Search Sentinel-2 STAC API.

The default Collection 1 product supplies native-resolution COG assets without
an account. Imagery supports inspection of terrestrial energy installations;
it is not an estimate of generated power or a reproduction of Dunnett (2020).
Source: https://github.com/Element84/earth-search.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urljoin, urlsplit

import pandas as pd

from .ground_raster import GroundImage, read_ground_image
from .http_base import DownloadReceipt, HttpConnector


def _bbox(value: Sequence[float]) -> list[float]:
    if (
        isinstance(value, (str, bytes))
        or len(value) != 4
        or any(isinstance(x, bool) for x in value)
    ):
        raise ValueError("bbox must be (west, south, east, north) in WGS84 degrees")
    try:
        west, south, east, north = map(float, value)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox must contain four finite coordinates") from exc
    if not all(math.isfinite(x) for x in (west, south, east, north)):
        raise ValueError("bbox must contain four finite coordinates")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("bbox must have west < east and south < north; split antimeridian AOIs")
    return [west, south, east, north]


def _utc(value: str) -> pd.Timestamp:
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Time bounds must be valid ISO dates or timestamps") from exc
    if not isinstance(result, pd.Timestamp) or pd.isna(result):
        raise ValueError("Time bounds must be finite dates")
    return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")


def _https(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Source URLs must use HTTPS without embedded credentials")
    return url


def _items(document: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        raise ValueError("Expected a STAC FeatureCollection object")
    features = document.get("features")
    if document.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise ValueError("Expected a STAC FeatureCollection with a features list")
    for feature in features:
        if (
            not isinstance(feature, dict)
            or feature.get("type") != "Feature"
            or not isinstance(feature.get("id"), str)
            or not isinstance(feature.get("properties"), dict)
            or not isinstance(feature.get("assets"), dict)
        ):
            raise ValueError("Invalid STAC item: id, properties and assets are required")
    return features


class Sentinel2GroundConnector(HttpConnector):
    """Search Sentinel-2 Collection 1 and retrieve ground-image assets.

    Search needs only the base installation. Windowed reading needs the
    optional ``ground`` extra (Rasterio). STAC item metadata stays intact,
    including each asset's native resolution, calibration and nodata values.
    The provider's scene-wide cloud percentage is not an AOI cloud mask.
    """

    API = "https://earth-search.aws.element84.com/v1"
    COLLECTION = "sentinel-2-c1-l2a"

    def search(
        self,
        *,
        bbox: Sequence[float],
        time_min: str,
        time_max: str,
        max_cloud_cover: float = 20.0,
        max_items: int = 20,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Return a bounded STAC FeatureCollection, clearest scenes first.

        ``bbox`` is west/south/east/north in WGS84 degrees. Time bounds are
        inclusive UTC instants, as in STAC; a date alone means midnight.
        ``max_items`` caps unique items, not pages. ``context.limit_reached``
        flags a filled cap: this result must not be assumed exhaustive.

        POST/GET pagination is followed with its declared body/merge semantics.
        Cached snapshots preserve full item metadata and a SHA-256 sidecar
        binding the file to this query. A changed query or damaged snapshot
        raises an error; ``refresh=True`` explicitly replaces the snapshot.
        """
        bounds = _bbox(bbox)
        start, stop = _utc(time_min), _utc(time_max)
        if stop <= start:
            raise ValueError("time_max must be later than time_min")
        if (
            isinstance(max_cloud_cover, bool)
            or not math.isfinite(max_cloud_cover)
            or not 0 <= max_cloud_cover <= 100
        ):
            raise ValueError("max_cloud_cover must be finite and between 0 and 100")
        if (
            isinstance(max_items, bool)
            or not isinstance(max_items, int)
            or not 1 <= max_items <= 10_000
        ):
            raise ValueError("max_items must be an integer between 1 and 10000")
        query = {
            "collections": [self.COLLECTION],
            "bbox": bounds,
            "datetime": f"{start.isoformat()}/{stop.isoformat()}",
            "limit": min(100, max_items),
            "query": {"eo:cloud_cover": {"lte": float(max_cloud_cover)}},
            "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        }
        request_identity = {"endpoint": self.API, "search": query, "max_items": max_items}
        path = Path(cache_path) if cache_path is not None else None
        sidecar = path.with_suffix(path.suffix + ".meta.json") if path is not None else None
        if path is not None and path.exists() and not refresh:
            if sidecar is None or not sidecar.exists():
                raise ValueError("STAC cache has no provenance sidecar; use refresh=True")
            provenance = json.loads(sidecar.read_text(encoding="utf-8"))
            content = path.read_bytes()
            if not isinstance(provenance, dict) or provenance.get("request") != request_identity:
                raise ValueError("STAC cache belongs to a different query; use a new cache path")
            if provenance.get("sha256") != sha256(content).hexdigest():
                raise ValueError("STAC cache SHA-256 does not match its provenance")
            result = json.loads(content)
            _items(result)
            return result

        url = _https(f"{self.API}/search")
        method, body = "POST", query
        selected: list[dict[str, Any]] = []
        seen_items: set[tuple[str, str]] = set()
        seen_pages: set[str] = set()
        receipts: list[dict[str, Any]] = []
        matched: int | None = None
        while True:
            signature = json.dumps([method, url, body], sort_keys=True)
            if signature in seen_pages or len(seen_pages) >= 1000:
                raise ValueError("STAC pagination repeated or exceeded 1000 pages")
            seen_pages.add(signature)
            response = self._client.request(method, url, json=body if method == "POST" else None)
            response.raise_for_status()
            page = response.json()
            features = _items(page)
            receipts.append(
                asdict(self.receipt("Earth Search STAC page", str(response.url), response.content))
            )
            context = page.get("context", {})
            if matched is None and isinstance(context, dict):
                count = context.get("matched", page.get("numberMatched"))
                if isinstance(count, int):
                    matched = count
            for item in features:
                key = (item.get("collection", ""), item["id"])
                if key not in seen_items:
                    seen_items.add(key)
                    selected.append(item)
                if len(selected) >= max_items:
                    break
            if len(selected) >= max_items:
                break
            links = page.get("links", [])
            if not isinstance(links, list):
                raise ValueError("Invalid STAC pagination links")
            next_links = [
                link for link in links if isinstance(link, dict) and link.get("rel") == "next"
            ]
            if not next_links:
                break
            if len(next_links) != 1:
                raise ValueError("Ambiguous STAC pagination: multiple next links")
            link = next_links[0]
            href = link.get("href")
            if not isinstance(href, str):
                raise ValueError("STAC next link must have an href")
            next_url = _https(urljoin(str(response.url), href))
            if urlsplit(next_url).netloc != urlsplit(self.API).netloc:
                raise ValueError("STAC next link points to a different host")
            next_method = str(link.get("method", "GET")).upper()
            if next_method not in {"GET", "POST"}:
                raise ValueError("STAC next link must use GET or POST")
            next_body = link.get("body", {})
            if not isinstance(next_body, dict):
                raise ValueError("STAC next-link body must be an object")
            if next_method == "GET" and next_body:
                raise ValueError("STAC GET pagination must carry parameters in its href")
            body = {**body, **next_body} if link.get("merge", False) else next_body
            method, url = next_method, next_url

        result = {
            "type": "FeatureCollection",
            "features": selected,
            "links": [{"rel": "root", "href": self.API}],
            "context": {
                "returned": len(selected),
                "matched": matched,
                "limit": max_items,
                "limit_reached": len(selected) >= max_items,
            },
        }
        if path is not None and sidecar is not None:
            content = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8")
            provenance = {
                **asdict(
                    self.receipt(
                        "Earth Search STAC snapshot", f"{self.API}/search", content, path=path
                    )
                ),
                "request": request_identity,
                "pages": receipts,
                "documentation": "https://github.com/Element84/earth-search",
                "attribution": "Contains Copernicus Sentinel data, processed by Element 84",
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            sidecar.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        return result

    @staticmethod
    def read_image(
        item: dict[str, Any],
        *,
        bbox: Sequence[float],
        asset: str = "visual",
        max_pixels: int = 4_000_000,
    ) -> GroundImage:
        """Read a native-resolution COG window; see :func:`read_ground_image`."""
        west, south, east, north = _bbox(bbox)
        return read_ground_image(
            item, bbox=(west, south, east, north), asset=asset, max_pixels=max_pixels
        )

    def download_asset(
        self,
        item: dict[str, Any],
        asset: str,
        destination: str | Path,
        *,
        max_bytes: int = 1_000_000_000,
        overwrite: bool = False,
    ) -> DownloadReceipt:
        """Stream a complete asset to disk with a checksum/provenance sidecar.

        Full Sentinel-2 bands can be hundreds of MB. Prefer ``read_image`` for
        farm-sized areas. The size ceiling is enforced while streaming, and a
        failed request never replaces an existing destination.
        """
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        metadata = item.get("assets", {}).get(asset)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("href"), str):
            raise ValueError(f"STAC item has no asset {asset!r} with a source URL")
        url = _https(metadata["href"])
        path = Path(destination)
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        if not overwrite and (path.exists() or sidecar.exists()):
            raise FileExistsError(f"Destination already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        checksum, size = sha256(), 0
        try:
            with self._client.stream("GET", url) as response:
                response.raise_for_status()
                announced = response.headers.get("Content-Length")
                if announced is not None and int(announced) > max_bytes:
                    raise ValueError("Asset exceeds max_bytes; use a windowed image read")
                with NamedTemporaryFile(
                    dir=path.parent, prefix=f".{path.name}.", delete=False
                ) as file:
                    temporary = Path(file.name)
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("Asset exceeds max_bytes; use a windowed image read")
                        checksum.update(chunk)
                        file.write(chunk)
                if not size:
                    raise ValueError("Source returned an empty asset")
                receipt = DownloadReceipt(
                    "Earth Search Sentinel-2 asset",
                    str(response.url),
                    datetime.now(UTC).isoformat(),
                    checksum.hexdigest(),
                    size,
                    str(path),
                )
            provenance = {
                **asdict(receipt),
                "item": item,
                "asset_key": asset,
                "attribution": "Contains Copernicus Sentinel data, processed by Element 84",
            }
            metadata_text = json.dumps(provenance, indent=2, allow_nan=False) + "\n"
            temporary.replace(path)
            temporary = None
            sidecar.write_text(metadata_text, encoding="utf-8")
            return receipt
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
