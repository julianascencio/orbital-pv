"""Versioned ground-PV inventories, aerial imagery, and weather satellites.

Downloads preserve original bytes and a checksum/provenance sidecar. Catalog
coverage, acquisition time, source licenses and engineering measurements are
different concepts: no inventory or rendered map is promoted to ground truth.
Network clients accept an HTTPX client for deterministic offline contract tests.
"""

from __future__ import annotations

import importlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from itertools import islice
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from uuid import UUID
from xml.etree import ElementTree
from zipfile import ZipFile

import httpx
import pandas as pd

from .ground_imagery import _bbox, _https, _items, _utc
from .http_base import DownloadReceipt, HttpConnector


def _positive_integer(value: int, name: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must not exceed {maximum}")
    return value


def _public_url(url: str) -> str:
    """Never persist transient signed URLs or authentication query strings."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _stream_to_file(
    chunks,
    destination: str | Path,
    *,
    source: str,
    url: str,
    metadata: Mapping[str, Any],
    max_bytes: int,
    overwrite: bool,
    expected_sha256: str | None = None,
) -> DownloadReceipt:
    _positive_integer(max_bytes, "max_bytes")
    path = Path(destination)
    sidecar = path.with_suffix(path.suffix + ".meta.json")
    if not overwrite and (path.exists() or sidecar.exists()):
        raise FileExistsError(f"Destination already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    digest, size = sha256(), 0
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as file:
            temporary = Path(file.name)
            for chunk in chunks:
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("Download exceeds max_bytes")
                digest.update(chunk)
                file.write(chunk)
        if size == 0:
            raise ValueError("Source returned an empty file")
        if expected_sha256 is not None and digest.hexdigest() != expected_sha256:
            raise ValueError("Downloaded SHA-256 does not match the expected source checksum")
        receipt = DownloadReceipt(
            source,
            _public_url(url),
            datetime.now(UTC).isoformat(),
            digest.hexdigest(),
            size,
            str(path),
        )
        provenance = {**asdict(receipt), **deepcopy(dict(metadata))}
        # Validate the sidecar before replacing an existing destination.
        serialized = json.dumps(provenance, indent=2, allow_nan=False) + "\n"
        temporary.replace(path)
        temporary = None
        sidecar.write_text(serialized, encoding="utf-8")
        return receipt
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class _ResearchHTTP(HttpConnector):
    def __init__(self, *, client: httpx.Client | None = None, timeout_s: float = 60.0):
        self._owns_client = client is None
        if client is None:
            super().__init__(timeout_s=timeout_s)
        else:
            self._client = client

    def close(self) -> None:
        if self._owns_client:
            super().close()

    def _download(
        self,
        url: str,
        destination: str | Path,
        *,
        source: str,
        metadata: Mapping[str, Any],
        max_bytes: int = 1_000_000_000,
        overwrite: bool = False,
        headers: Mapping[str, str] | None = None,
        expected_sha256: str | None = None,
    ) -> DownloadReceipt:
        _https(url)
        _positive_integer(max_bytes, "max_bytes")
        path = Path(destination)
        if not overwrite and (
            path.exists() or path.with_suffix(path.suffix + ".meta.json").exists()
        ):
            raise FileExistsError(f"Destination already exists: {path}")
        with self._client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            if int(response.headers.get("Content-Length", "0")) > max_bytes:
                raise ValueError("Download exceeds max_bytes")
            return _stream_to_file(
                response.iter_bytes(),
                path,
                source=source,
                url=url,
                metadata=metadata,
                max_bytes=max_bytes,
                overwrite=overwrite,
                expected_sha256=expected_sha256,
            )


class PNOAConnector(_ResearchHTTP):
    """IGN PNOA original COG downloads and explicitly rendered WMS images.

    Select original COG URLs from the CNIG catalog. WMS is a display product:
    the requested width/height is not a claim of native spatial resolution.
    See https://pnoa.ign.es/web/portal/pnoa-imagen/visualizadores-y-servicios-web.
    """

    LATEST = "https://www.ign.es/wms-inspire/pnoa-ma"
    HISTORICAL = "https://www.ign.es/wms/pnoa-historico"
    LICENSE = "CC-BY-4.0-compatible IGN license; retain product/date/producer attribution"

    def layers(self, *, historical: bool = False) -> list[dict[str, str]]:
        endpoint = self.HISTORICAL if historical else self.LATEST
        response = self._client.get(
            endpoint, params={"SERVICE": "WMS", "REQUEST": "GetCapabilities"}
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        result = []
        for layer in root.iter():
            if layer.tag.rsplit("}", 1)[-1] == "Layer":
                fields = {child.tag.rsplit("}", 1)[-1]: child.text for child in layer}
                name = fields.get("Name")
                if name:
                    result.append({"name": name, "title": fields.get("Title") or ""})
        return result

    def download_original(
        self,
        url: str,
        destination: str | Path,
        *,
        acquisition_date: str,
        attribution: str,
        max_bytes: int = 1_000_000_000,
        overwrite: bool = False,
        expected_sha256: str | None = None,
    ) -> DownloadReceipt:
        """Download a caller-selected IGN/CNIG original, without resampling."""
        host = urlsplit(_https(url)).hostname or ""
        if not (
            host == "ign.es"
            or host.endswith(".ign.es")
            or host == "cnig.es"
            or host.endswith(".cnig.es")
        ):
            raise ValueError("PNOA original URL must belong to IGN or CNIG")
        if not acquisition_date.strip() or not attribution.strip():
            raise ValueError("Acquisition date and original product attribution are required")
        return self._download(
            url,
            destination,
            source="IGN/CNIG PNOA original",
            max_bytes=max_bytes,
            overwrite=overwrite,
            expected_sha256=expected_sha256,
            metadata={
                "acquisition_date": acquisition_date,
                "attribution": attribution,
                "license": self.LICENSE,
                "product_kind": "original_imagery",
            },
        )

    def download_map(
        self,
        destination: str | Path,
        *,
        bbox: Sequence[float],
        layer: str,
        width: int = 1024,
        height: int = 1024,
        historical: bool = False,
        acquisition_date: str = "mixed_or_unknown; inspect original metadata",
        overwrite: bool = False,
    ) -> DownloadReceipt:
        """Save a WMS PNG using explicit longitude/latitude WMS 1.1.1 axes."""
        bounds = _bbox(bbox)
        _positive_integer(width, "width", 4096)
        _positive_integer(height, "height", 4096)
        if not isinstance(layer, str) or not layer.strip():
            raise ValueError("Choose a named layer from layers()")
        endpoint = self.HISTORICAL if historical else self.LATEST
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetMap",
            "LAYERS": layer,
            "STYLES": "",
            "SRS": "EPSG:4326",
            "BBOX": ",".join(map(str, bounds)),
            "WIDTH": width,
            "HEIGHT": height,
            "FORMAT": "image/png",
        }
        path = Path(destination)
        if not overwrite and (
            path.exists() or path.with_suffix(path.suffix + ".meta.json").exists()
        ):
            raise FileExistsError(f"Destination already exists: {path}")
        response = self._client.get(endpoint, params=params)
        response.raise_for_status()
        if not response.content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNOA returned a WMS error or a non-PNG response")
        return _stream_to_file(
            [response.content],
            path,
            source="IGN PNOA WMS rendered map",
            url=endpoint,
            metadata={
                "request": params,
                "bbox_wgs84": bounds,
                "acquisition_date": acquisition_date,
                "license": self.LICENSE,
                "product_kind": "rendered_display",
                "native_resolution_m": None,
                "not_calibrated_reflectance": True,
            },
            max_bytes=100_000_000,
            overwrite=overwrite,
        )


class CopernicusDataSpaceConnector(_ResearchHTTP):
    """Current CDSE STAC discovery and authenticated OData product retrieval.

    Catalog queries are public. Product download requires an explicit access
    token obtained using the user's CDSE account; it is never written to disk.
    S3 URLs in STAC are retained verbatim, not falsely treated as public HTTPS.
    """

    API = "https://stac.dataspace.copernicus.eu/v1"

    def collections(self) -> dict[str, Any]:
        response = self._client.get(f"{self.API}/collections")
        response.raise_for_status()
        return response.json()

    def search(
        self,
        *,
        bbox: Sequence[float],
        time_min: str,
        time_max: str,
        collection: str = "sentinel-2-l2a",
        max_items: int = 50,
        max_cloud_cover: float | None = 20.0,
    ) -> dict[str, Any]:
        bounds, start, stop = _bbox(bbox), _utc(time_min), _utc(time_max)
        if stop <= start:
            raise ValueError("time_max must be later than time_min")
        _positive_integer(max_items, "max_items", 10_000)
        if not collection or not isinstance(collection, str):
            raise ValueError("collection must be a nonempty catalog collection ID")
        body: dict[str, Any] = {
            "collections": [collection],
            "bbox": bounds,
            "datetime": f"{start.isoformat()}/{stop.isoformat()}",
            "limit": min(100, max_items),
        }
        if max_cloud_cover is not None:
            if (
                isinstance(max_cloud_cover, bool)
                or not math.isfinite(max_cloud_cover)
                or not 0 <= max_cloud_cover <= 100
            ):
                raise ValueError("max_cloud_cover must be between zero and 100")
            body["query"] = {"eo:cloud_cover": {"lte": max_cloud_cover}}
        original = deepcopy(body)
        method, url = "POST", f"{self.API}/search"
        features, seen, pages = [], set(), set()
        has_more = False
        while True:
            signature = json.dumps([method, url, body], sort_keys=True)
            if signature in pages or len(pages) >= 1000:
                raise ValueError("STAC pagination repeated or exceeded 1000 pages")
            pages.add(signature)
            response = self._client.request(method, url, json=body if method == "POST" else None)
            response.raise_for_status()
            page = response.json()
            for item in _items(page):
                key = (item.get("collection", collection), item["id"])
                if key not in seen:
                    features.append(item)
                    seen.add(key)
                if len(features) >= max_items:
                    break
            links = [x for x in page.get("links", []) if x.get("rel") == "next"]
            has_more = bool(links)
            if len(features) >= max_items or not links:
                break
            if len(links) != 1:
                raise ValueError("Ambiguous STAC pagination")
            link = links[0]
            url = _https(urljoin(str(response.url), link["href"]))
            if urlsplit(url).hostname != urlsplit(self.API).hostname:
                raise ValueError("STAC pagination changed host")
            method = link.get("method", "GET").upper()
            new_body = link.get("body", {})
            if method not in {"GET", "POST"} or not isinstance(new_body, dict):
                raise ValueError("Invalid STAC pagination method/body")
            if method == "GET" and new_body:
                raise ValueError("GET pagination cannot carry a request body")
            body = {**body, **new_body} if link.get("merge") else new_body
        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "source": self.API,
                "request": original,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "license": "Copernicus Sentinel data terms; inspect each collection",
                "returned": len(features),
                "limit_reached": len(features) == max_items,
                "next_page_advertised": has_more,
            },
        }

    def download_product(
        self,
        product_id: str,
        destination: str | Path,
        *,
        access_token: str,
        max_bytes: int = 5_000_000_000,
        overwrite: bool = False,
    ) -> DownloadReceipt:
        identifier = str(UUID(product_id))
        if not access_token or not access_token.strip():
            raise ValueError("An explicit CDSE OAuth access token is required")
        url = f"https://download.dataspace.copernicus.eu/odata/v1/Products({identifier})/$value"
        return self._download(
            url,
            destination,
            source="Copernicus Data Space original product",
            metadata={"product_id": identifier, "license": "Copernicus Sentinel data terms"},
            headers={"Authorization": f"Bearer {access_token}"},
            max_bytes=max_bytes,
            overwrite=overwrite,
        )


@dataclass(frozen=True, slots=True)
class InventoryAsset:
    provider: str
    version: str
    url: str
    license: str
    citation: str
    observation_period: str


class PVInventoryConnector(_ResearchHTTP):
    """Download pinned GRW, GM-SEUS, and ANDPI inventory releases.

    The multi-GB GM-SEUS archive is downloaded only on explicit request.
    A spatial subset is not independent validation of a model trained on it.
    """

    @staticmethod
    def asset(provider: str, *, year: int = 2025) -> InventoryAsset:
        name = provider.lower()
        if name == "grw":
            return InventoryAsset(
                "Global Renewables Watch",
                "v1.0-2024q2",
                "https://github.com/microsoft/global-renewables-watch/releases/download/v1.0/solar_all_2024q2_v1.gpkg",
                "See GRW release terms; source Planet imagery is not included",
                "https://doi.org/10.48550/arXiv.2503.14860",
                "2017Q4-2024Q2",
            )
        if name == "gmseus":
            return InventoryAsset(
                "GM-SEUS",
                "v2.1-2026-07-19",
                "https://zenodo.org/records/21445384/files/GMSEUS.zip",
                "Original content CC-BY-4.0; upstream ODbL/NC terms retained per Source/sourceDataLicenses.csv",
                "https://doi.org/10.1038/s41597-025-05862-4",
                "Imagery through 2025; selected metadata updated 2026",
            )
        if name == "andpi":
            if isinstance(year, bool) or not isinstance(year, int) or not 2019 <= year <= 2025:
                raise ValueError("Published ANDPI inventory year must be 2019-2025")
            return InventoryAsset(
                "ANDPI Fusion PV Mapping",
                f"zenodo-20686002-{year}",
                f"https://zenodo.org/records/20686002/files/World_PV_power_plants_{year}.zip",
                "CC-BY-4.0 (Zenodo record); retain upstream inventory terms and source attribution",
                "https://doi.org/10.1016/j.jag.2025.105005",
                "2025Q2" if year == 2025 else str(year),
            )
        raise ValueError("provider must be grw, gmseus or andpi")

    def download(
        self,
        provider: str,
        destination: str | Path,
        *,
        year: int = 2025,
        max_bytes: int = 5_000_000_000,
        overwrite: bool = False,
        expected_sha256: str | None = None,
    ) -> DownloadReceipt:
        asset = self.asset(provider, year=year)
        return self._download(
            asset.url,
            destination,
            source=asset.provider,
            metadata={"inventory": asdict(asset)},
            max_bytes=max_bytes,
            overwrite=overwrite,
            expected_sha256=expected_sha256,
        )


def load_pv_inventory(
    path: str | Path,
    *,
    bbox: Sequence[float] | None = None,
    layer: str | None = None,
    archive_member: str | None = None,
    max_features: int = 100_000,
) -> dict[str, Any]:
    """Load/subset GeoJSON or optional GeoPackage/Shapefile using original CRS.

    Non-GeoJSON uses geopandas/pyogrio lazily. For a ZIP select its vector member
    explicitly; no files are extracted into the working directory. Raw source
    fields (including Source/license/measurement provenance) are not renamed.
    An available download sidecar is checksum-verified before reading.
    """
    file = Path(path)
    _positive_integer(max_features, "max_features")
    bounds = _bbox(bbox) if bbox is not None else None
    provenance: dict[str, Any] = {
        "local_path": str(file),
        "license": "unknown; inspect source terms",
    }
    sidecar = file.with_suffix(file.suffix + ".meta.json")
    if sidecar.exists():
        provenance = json.loads(sidecar.read_text())
        with file.open("rb") as stream:
            digest = sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != provenance.get("sha256"):
            raise ValueError("Inventory checksum differs from its provenance sidecar")
    if file.suffix.lower() in {".json", ".geojson"}:
        result = json.loads(file.read_text())
        if result.get("type") != "FeatureCollection" or not isinstance(
            result.get("features"), list
        ):
            raise ValueError("Expected a GeoJSON FeatureCollection")
        if result.get("crs") is not None:
            raise ValueError("GeoJSON must use RFC 7946 WGS84; reproject legacy CRS explicitly")
        features = result["features"]
        if bounds is not None:
            geometry = importlib.import_module("shapely.geometry")
            region = geometry.box(*bounds)
            features = [
                f
                for f in features
                if f.get("geometry") and geometry.shape(f["geometry"]).intersects(region)
            ]
        truncated = len(features) > max_features
        result["features"] = features[:max_features]
    else:
        try:
            gpd = importlib.import_module("geopandas")
        except ImportError as exc:
            raise ImportError(
                "Vector inventories require geopandas and pyogrio; install orbital-pv[ground-research]"
            ) from exc
        uri = str(file)
        if file.suffix.lower() == ".zip":
            with ZipFile(file) as archive:
                candidates = [
                    n
                    for n in archive.namelist()
                    if n.lower().endswith((".gpkg", ".shp", ".geojson"))
                ]
                if archive_member is None:
                    if len(candidates) != 1:
                        raise ValueError("Select archive_member explicitly from the inventory ZIP")
                    archive_member = candidates[0]
                member = PurePosixPath(archive_member)
                if member.is_absolute() or ".." in member.parts or archive_member not in candidates:
                    raise ValueError("Invalid or missing inventory archive member")
                uri = f"zip://{file.resolve()}!{archive_member}"
        # Passing a GeoSeries lets geopandas transform the spatial filter to the
        # file CRS with Fiona; pyogrio needs the CRS explicitly, so inspect it.
        pyogrio = importlib.import_module("pyogrio")
        info = pyogrio.read_info(uri, layer=layer)
        read_bbox = None
        if bounds is not None:
            projection = importlib.import_module("pyproj")
            if not info.get("crs"):
                raise ValueError("Source vector CRS is missing")
            transformer = projection.Transformer.from_crs("EPSG:4326", info["crs"], always_xy=True)
            west, south, east, north = bounds
            read_bbox = transformer.transform_bounds(west, south, east, north)
        frame = gpd.read_file(
            uri, layer=layer, bbox=read_bbox, rows=max_features + 1, engine="pyogrio"
        )
        if frame.crs is None:
            raise ValueError("Source vector CRS is missing")
        potentially_truncated = len(frame) > max_features
        frame = frame.to_crs("EPSG:4326")
        if bounds is not None:
            geometry = importlib.import_module("shapely.geometry")
            frame = frame[frame.intersects(geometry.box(*bounds))]
        truncated = potentially_truncated or len(frame) > max_features
        result = json.loads(frame.iloc[:max_features].to_json())
    result["metadata"] = {
        **result.get("metadata", {}),
        "source": provenance,
        "bbox_wgs84": bounds,
        "limit_reached": truncated,
        "crs": "EPSG:4326",
        "attribute_status": "source_fields_retained; inferred values are not measurements",
    }
    return result


class GoesABIConnector(_ResearchHTTP):
    """Anonymous NOAA GOES-R ABI original-netCDF listing and downloads.

    Select the satellite explicitly for the observation date. Listing a
    satellite does not assume that it was the operational GOES-East then.
    Source: https://registry.opendata.aws/noaa-goes/.
    """

    @staticmethod
    def _bucket(satellite: int) -> str:
        if (
            isinstance(satellite, bool)
            or not isinstance(satellite, int)
            or satellite not in (16, 17, 18, 19)
        ):
            raise ValueError("satellite must be GOES 16, 17, 18 or 19")
        return f"https://noaa-goes{satellite}.s3.amazonaws.com"

    def search(
        self,
        *,
        satellite: int,
        product: str,
        time_min: str,
        time_max: str,
        max_items: int = 100,
    ) -> dict[str, Any]:
        base = self._bucket(satellite)
        if not isinstance(product, str) or not re.fullmatch(r"ABI-[A-Za-z0-9-]+", product):
            raise ValueError("product must be an ABI product prefix, e.g. ABI-L2-CMIPF")
        start, stop = _utc(time_min), _utc(time_max)
        if stop <= start or stop - start > pd.Timedelta(days=31):
            raise ValueError("GOES search interval must be positive and no longer than 31 days")
        _positive_integer(max_items, "max_items", 100_000)
        items, seen = [], set()
        for hour in pd.date_range(start.floor("h"), stop.ceil("h"), inclusive="left", freq="h"):
            prefix = f"{product}/{hour.year}/{hour.day_of_year:03d}/{hour.hour:02d}/"
            token: str | None = None
            tokens: set[str] = set()
            while True:
                params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
                if token:
                    params["continuation-token"] = token
                response = self._client.get(base, params=params)
                response.raise_for_status()
                root = ElementTree.fromstring(response.content)
                for entry in root.findall("{*}Contents"):
                    key = entry.findtext("{*}Key") or ""
                    match = re.search(r"_s(\d{13})(\d*)_", key)
                    if not key.startswith(prefix) or not match or not key.endswith(".nc"):
                        continue
                    observed = pd.Timestamp(datetime.strptime(match[1], "%Y%j%H%M%S"), tz="UTC")
                    if match[2]:
                        observed += pd.Timedelta(seconds=float("0." + match[2]))
                    if not start <= observed < stop or key in seen:
                        continue
                    seen.add(key)
                    items.append(
                        {
                            "key": key,
                            "url": f"{base}/{quote(key, safe='/')}",
                            "satellite": satellite,
                            "product": product,
                            "time_start": observed.isoformat(),
                            "bytes": int(entry.findtext("{*}Size") or 0),
                            "etag": entry.findtext("{*}ETag"),
                            "etag_is_sha256": False,
                        }
                    )
                    if len(items) >= max_items:
                        break
                if len(items) >= max_items or root.findtext("{*}IsTruncated") != "true":
                    break
                token = root.findtext("{*}NextContinuationToken")
                if not token or token in tokens:
                    raise ValueError("Invalid or repeated S3 continuation token")
                tokens.add(token)
            if len(items) >= max_items:
                break
        return {
            "items": items,
            "metadata": {
                "source": base,
                "product": product,
                "time_min": start.isoformat(),
                "time_max_exclusive": stop.isoformat(),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "limit_reached": len(items) >= max_items,
                "license": "NOAA open data; attribute NOAA; no endorsement implied",
            },
        }

    def download(
        self,
        item: Mapping[str, Any],
        destination: str | Path,
        *,
        max_bytes: int = 1_000_000_000,
        overwrite: bool = False,
    ) -> DownloadReceipt:
        base = self._bucket(item["satellite"])
        key = item["key"]
        if (
            not isinstance(key, str)
            or not key.startswith("ABI-")
            or ".." in PurePosixPath(key).parts
        ):
            raise ValueError("Invalid GOES ABI object key")
        url = f"{base}/{quote(key, safe='/')}"
        return self._download(
            url,
            destination,
            source="NOAA GOES ABI original netCDF",
            metadata={
                "item": dict(item),
                "license": "NOAA open data",
                "product_kind": "original_satellite_product; not ground PV power",
            },
            max_bytes=max_bytes,
            overwrite=overwrite,
        )


class EumetsatConnector:
    """Thin, working EUMDAC SDK adapter with explicit account credentials.

    EUMDAC is imported only when this connector is created without an injected
    SDK store. Authentication, license checks and token refresh remain with
    the official SDK. It is not an anonymous-access or license-bypass wrapper.
    Source: https://gitlab.eumetsat.int/eumetlab/data-services/eumdac.
    """

    def __init__(
        self,
        *,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        datastore: Any = None,
    ):
        if datastore is not None:
            self._store = datastore
        else:
            if not consumer_key or not consumer_secret:
                raise ValueError(
                    "Explicit EUMETSAT credentials consumer_key and consumer_secret are required"
                )
            try:
                sdk = importlib.import_module("eumdac")
            except ImportError as exc:
                raise ImportError(
                    "Install eumdac or orbital-pv[ground-research] for EUMETSAT"
                ) from exc
            self._store = sdk.DataStore(sdk.AccessToken((consumer_key, consumer_secret)))

    def search(
        self,
        *,
        collection: str,
        time_min: str,
        time_max: str,
        bbox: Sequence[float] | None = None,
        max_items: int = 20,
    ) -> list[Any]:
        start, stop = _utc(time_min), _utc(time_max)
        if stop <= start:
            raise ValueError("time_max must be later than time_min")
        _positive_integer(max_items, "max_items", 10_000)
        if not isinstance(collection, str) or not collection.startswith("EO:EUM:DAT:"):
            raise ValueError("Use an explicit EUMETSAT collection ID")
        filters: dict[str, Any] = {"dtstart": start.to_pydatetime(), "dtend": stop.to_pydatetime()}
        if bbox is not None:
            filters["bbox"] = ",".join(map(str, _bbox(bbox)))
        products = self._store.get_collection(collection).search(**filters)
        # A full list of max_items is potentially truncated, never exhaustive.
        return list(islice(products, max_items))

    @staticmethod
    def download_product(
        product: Any,
        destination: str | Path,
        *,
        collection: str,
        license_name: str,
        max_bytes: int = 5_000_000_000,
        overwrite: bool = False,
    ) -> DownloadReceipt:
        if not license_name.strip() or not collection.startswith("EO:EUM:DAT:"):
            raise ValueError("The collection and applicable data license are required")
        _positive_integer(max_bytes, "max_bytes")
        path = Path(destination)
        if not overwrite and (
            path.exists() or path.with_suffix(path.suffix + ".meta.json").exists()
        ):
            raise FileExistsError(f"Destination already exists: {path}")
        with product.open() as source:
            return _stream_to_file(
                iter(lambda: source.read(1024 * 1024), b""),
                path,
                source="EUMETSAT original product via EUMDAC",
                url=f"https://data.eumetsat.int/product/{quote(collection, safe=':')}",
                metadata={
                    "product_id": str(product),
                    "collection": collection,
                    "license": license_name,
                    "authentication": "user-supplied EUMDAC credentials",
                },
                max_bytes=max_bytes,
                overwrite=overwrite,
            )


__all__ = [
    "CopernicusDataSpaceConnector",
    "EumetsatConnector",
    "GoesABIConnector",
    "InventoryAsset",
    "PNOAConnector",
    "PVInventoryConnector",
    "load_pv_inventory",
]
