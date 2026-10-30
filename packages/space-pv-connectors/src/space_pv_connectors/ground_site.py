"""Reusable, provenance-checked inputs for inspecting terrestrial PV sites."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from .ground_imagery import Sentinel2GroundConnector
from .ground_osm import OpenStreetMapEnergyConnector, _bounded_bbox
from .ground_raster import GroundImage, load_ground_image
from .http_base import HttpConnector


@dataclass(frozen=True, slots=True)
class PVSite:
    """Source imagery and mapped solar features for one inspection area.

    ``images`` contains native-grid :class:`GroundImage` objects keyed by STAC
    asset name. ``item`` is the selected scene from the bounded ``scenes``
    search, and ``osm`` is the original Overpass response. Each image keeps its
    own resolution, mask and calibration; the map and image dates can differ.

    The name is a display label, not a verified inventory record. Solar-tagged
    OSM features still need method-tag inspection before identifying them as
    photovoltaic. Neither this object nor its loader infers plant boundaries,
    panel area, capacity, generation or completeness of OSM mapping.
    """

    name: str
    bbox_wgs84: tuple[float, float, float, float]
    scenes: dict[str, Any]
    item: dict[str, Any]
    images: dict[str, GroundImage]
    osm: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        """Return JSON-serializable dates, search limits and native-grid facts.

        Pixel sizes use the units of the asset CRS. OSM counts describe raw
        objects, not unique plants; SCL counts describe source quality classes,
        not panel labels. Masked pixels are excluded from SCL counts.
        """
        result = {
            "name": self.name,
            "bbox_wgs84": list(self.bbox_wgs84),
            "scene_id": self.item["id"],
            "acquired_at": self.item["properties"].get("datetime"),
            "scene_cloud_cover_percent": self.item["properties"].get("eo:cloud_cover"),
            "search": deepcopy(self.scenes.get("context", {})),
            "osm_timestamp": self.osm.get("osm3s", {}).get("timestamp_osm_base"),
            "osm_element_counts": dict(
                Counter(element["type"] for element in self.osm["elements"])
            ),
            "images": {
                key: {
                    "shape": list(image.data.shape),
                    "dtype": str(image.data.dtype),
                    "crs": image.crs,
                    "pixel_size": [abs(image.transform[0]), abs(image.transform[4])],
                    "bounds": list(image.bounds),
                    "masked_band_samples": int(np.ma.getmaskarray(image.data).sum()),
                }
                for key, image in self.images.items()
            },
        }
        if "scl" in self.images:
            codes, counts = np.unique(self.images["scl"].data.compressed(), return_counts=True)
            result["scl_pixel_counts"] = dict(zip(codes.tolist(), counts.tolist(), strict=True))
        return result


def _component(value: str, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) is None:
        raise ValueError(f"{label} must contain only letters, numbers, underscores or hyphens")
    return value


def _deny_network(request: httpx.Request) -> httpx.Response:
    raise RuntimeError(
        "offline=True forbids network requests; restore the complete cached snapshot"
    )


def _offline_transport(connector: HttpConnector) -> None:
    # Cache loaders reuse the connectors' query/checksum validation. A blocked
    # transport also prevents a network fallback if a file disappears after
    # the initial existence check.
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(_deny_network))


def _check_crop(
    image: GroundImage,
    *,
    item: dict[str, Any],
    bbox: tuple[float, float, float, float],
    asset: str,
) -> None:
    if (
        image.scene_id != item["id"]
        or image.bbox_wgs84 != bbox
        or image.asset_key != asset
        or image.source_url != item["assets"][asset].get("href")
        or image.asset_metadata != item["assets"][asset]
        or image.item_metadata != item
    ):
        raise ValueError(
            "Cached crop belongs to a different scene, area, asset or source metadata; "
            "use a new cache prefix or refresh=True"
        )


def load_pv_site(
    *,
    bbox: Sequence[float],
    time_min: str,
    time_max: str,
    cache_dir: str | Path,
    name: str = "PV site",
    cache_prefix: str = "site",
    max_cloud_cover: float = 20.0,
    max_items: int = 10,
    scene_id: str | None = None,
    assets: Sequence[str] = ("visual", "red", "scl"),
    offline: bool = False,
    refresh: bool = False,
    timeout_s: float = 60.0,
    max_pixels: int = 4_000_000,
) -> PVSite:
    """Load or retrieve imagery and OSM inputs for a small PV inspection area.

    Search Sentinel-2 Collection 1, select the first (lowest scene-cloud-cover)
    returned item by default, load native crops, and retrieve raw solar-tagged
    OSM features. A supplied ``scene_id`` must occur in the bounded search.
    Search intersection does not guarantee full raster coverage; the underlying
    crop reader raises for tile-edge areas rather than mosaicking implicitly.

    ``bbox`` is WGS84 ``(west, south, east, north)`` and must satisfy the OSM
    connector's one-square-degree limit. Time bounds are inclusive UTC instants.
    Scene-wide cloud cover is not a local cloud mask. Inspect quality classes
    and ``site.scenes['context']['limit_reached']`` when selecting inputs.

    The cache contains ``{prefix}-scenes.json``, ``{prefix}-osm.json`` and
    ``{prefix}-{asset}.tif``, each with its provenance sidecar. Existing caches
    must match the request, SHA-256, selected scene, asset metadata and grid.
    Only missing files are retrieved; incomplete or inconsistent caches raise.
    ``refresh=True`` explicitly retrieves replacement snapshots and crops.
    A refresh is not a transaction across all files: if it fails, retry with
    refresh enabled or use a new cache prefix. Mixed snapshots fail validation.

    ``offline=True`` requires every source file and sidecar before any loading
    begins, blocks HTTP fallback, and cannot be combined with ``refresh=True``.
    ``max_pixels`` limits band samples per asset, not the sum across assets.
    Install ``orbital-pv[ground]`` for GeoTIFF support; plotting is separate.
    """
    bounds = _bounded_bbox(bbox)
    prefix = _component(cache_prefix, "cache_prefix")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a nonempty string")
    if isinstance(assets, (str, bytes)) or not assets:
        raise ValueError("assets must be a nonempty sequence of asset keys")
    selected_assets = tuple(_component(asset, "asset key") for asset in assets)
    if len(set(selected_assets)) != len(selected_assets):
        raise ValueError("assets must not contain duplicates")
    if not isinstance(offline, bool) or not isinstance(refresh, bool):
        raise ValueError("offline and refresh must be booleans")
    if offline and refresh:
        raise ValueError("offline=True cannot be combined with refresh=True")
    if scene_id is not None and (not isinstance(scene_id, str) or not scene_id):
        raise ValueError("scene_id must be a nonempty string or None")
    if isinstance(max_pixels, bool) or not isinstance(max_pixels, int) or max_pixels <= 0:
        raise ValueError("max_pixels must be a positive integer")
    if (
        isinstance(timeout_s, bool)
        or not isinstance(timeout_s, (int, float))
        or not math.isfinite(timeout_s)
        or timeout_s <= 0
    ):
        raise ValueError("timeout_s must be finite and positive")

    directory = Path(cache_dir)
    scenes_path, osm_path = (directory / f"{prefix}-{kind}.json" for kind in ("scenes", "osm"))
    crop_paths = {asset: directory / f"{prefix}-{asset}.tif" for asset in selected_assets}
    paths = [scenes_path, osm_path, *crop_paths.values()]
    for path in paths:
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        present = path.is_file(), sidecar.is_file()
        if offline and not all(present):
            raise FileNotFoundError(f"Offline snapshot requires {path} and {sidecar}")
        if not refresh and any(present) and not all(present):
            raise ValueError(f"Incomplete cached file/sidecar pair: {path}; use refresh=True")
    if not offline:
        directory.mkdir(parents=True, exist_ok=True)

    with Sentinel2GroundConnector(timeout_s=timeout_s) as connector:
        if offline:
            _offline_transport(connector)
        scenes = connector.search(
            bbox=bounds,
            time_min=time_min,
            time_max=time_max,
            max_cloud_cover=max_cloud_cover,
            max_items=max_items,
            cache_path=scenes_path,
            refresh=refresh,
        )
        if not scenes["features"]:
            raise LookupError("No matching Sentinel-2 scenes; widen the date range or cloud limit")
        item = scenes["features"][0]
        if scene_id is not None:
            matches = [candidate for candidate in scenes["features"] if candidate["id"] == scene_id]
            if not matches:
                raise LookupError("scene_id is absent from the bounded search; revise the search")
            item = matches[0]
        if any(not isinstance(item["assets"].get(asset), dict) for asset in selected_assets):
            raise ValueError("Selected scene does not contain every requested image asset")
        images = {}
        for asset, path in crop_paths.items():
            if path.is_file() and not refresh:
                image = load_ground_image(path, max_pixels=max_pixels)
            else:
                if offline:
                    raise FileNotFoundError(f"Offline crop disappeared while loading: {path}")
                image = connector.read_image(item, bbox=bounds, asset=asset, max_pixels=max_pixels)
                image.save_geotiff(path, overwrite=refresh)
            _check_crop(image, item=item, bbox=bounds, asset=asset)
            images[asset] = image
    with OpenStreetMapEnergyConnector(timeout_s=timeout_s) as connector:
        if offline:
            _offline_transport(connector)
        osm = connector.fetch_energy_features(
            bbox=bounds,
            sources=("solar",),
            cache_path=osm_path,
            refresh=refresh,
        )
    return PVSite(name=name, bbox_wgs84=bounds, scenes=scenes, item=item, images=images, osm=osm)
