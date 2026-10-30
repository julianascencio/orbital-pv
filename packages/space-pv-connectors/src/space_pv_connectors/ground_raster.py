"""Native-grid subsets of public ground-imaging Cloud Optimized GeoTIFFs.

Rasterio is optional and is imported only when reading or writing an image.
Pixels retain their source values, resolution and nodata mask. This module
does not infer farm boundaries, resample bands or classify cloudy pixels.
"""

from __future__ import annotations

import importlib
import json
import math
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import file_digest
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlsplit

import numpy as np

from .http_base import DownloadReceipt


def _rasterio() -> Any:
    try:
        return importlib.import_module("rasterio")
    except ImportError as exc:
        raise ImportError(
            "Ground image reading requires rasterio; install it with "
            "python -m pip install 'orbital-pv[ground]'."
        ) from exc


def _validate_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    try:
        if len(bbox) != 4 or any(isinstance(value, bool) for value in bbox):
            raise ValueError
        west, south, east, north = (float(value) for value in bbox)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox must contain (west, south, east, north) in WGS84 degrees") from exc
    if not all(math.isfinite(value) for value in (west, south, east, north)):
        raise ValueError("bbox values must be finite")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError(
            "bbox must satisfy -180 <= west < east <= 180 and -90 <= south < north <= 90; "
            "split antimeridian-crossing areas into separate requests"
        )
    return west, south, east, north


def _band_calibration(metadata: dict[str, Any], count: int) -> tuple[list[float], list[float]]:
    bands = metadata.get("raster:bands")
    if not isinstance(bands, list) or len(bands) != count:
        raise ValueError("One explicit raster:bands scale and offset is required per image band")
    scales: list[float] = []
    offsets: list[float] = []
    for band in bands:
        try:
            if not isinstance(band, dict):
                raise ValueError
            scale, offset = float(band["scale"]), float(band["offset"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Reflectance requires explicit raster:bands scale and offset") from exc
        if not math.isfinite(scale) or not math.isfinite(offset) or scale <= 0:
            raise ValueError("Reflectance scale must be finite and positive; offset must be finite")
        scales.append(scale)
        offsets.append(offset)
    return scales, offsets


def _same_nodata(values: tuple[float | None, ...]) -> bool:
    first = values[0]
    return all(
        value == first
        or (value is not None and first is not None and math.isnan(value) and math.isnan(first))
        for value in values
    )


@dataclass(frozen=True, slots=True)
class GroundImage:
    """A native-resolution rectangular crop, retaining raw pixel semantics.

    ``data`` has shape ``(bands, rows, columns)``; True mask entries mean
    missing data. ``transform`` holds affine ``(a, b, c, d, e, f)`` coefficients
    and ``bounds`` is ``(left, bottom, right, top)`` in ``crs``. Pixel-aligned
    bounds can extend slightly beyond the requested ``bbox_wgs84``.

    ``visual`` is a rendered RGB product, not calibrated reflectance.
    ``scl`` is a categorical scene-classification product, not a power or
    irradiance measurement. No cloud masking is applied implicitly.
    """

    data: np.ma.MaskedArray
    crs: str
    transform: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]
    scene_id: str
    asset_key: str
    source_url: str
    asset_metadata: dict[str, Any]
    bbox_wgs84: tuple[float, float, float, float]
    item_metadata: dict[str, Any]
    nodata_values: tuple[float | None, ...]
    retrieved_at: str

    def reflectance(self) -> np.ma.MaskedArray:
        """Return ``raw * scale + offset`` using explicit STAC band metadata.

        Only assets declaring the ``reflectance`` role are accepted. Missing
        data remain masked before calibration; negative reflectance values
        are retained. The raw ``data`` is never modified. For example,
        Collection 1 commonly declares scale 0.0001 and offset -0.1, so
        dividing every product by 10000 without its offset would be wrong.
        """
        if "reflectance" not in self.asset_metadata.get("roles", []):
            raise ValueError("This asset does not declare a reflectance role; use its raw data")
        scales, offsets = _band_calibration(self.asset_metadata, self.data.shape[0])
        scale = np.asarray(scales, dtype=np.float64)[:, None, None]
        offset = np.asarray(offsets, dtype=np.float64)[:, None, None]
        return np.ma.array(
            self.data.astype(np.float64) * scale + offset,
            mask=np.ma.getmaskarray(self.data),
            copy=False,
        )

    def save_geotiff(self, destination: str | Path, *, overwrite: bool = False) -> DownloadReceipt:
        """Save raw pixels, georeferencing, calibration and provenance.

        The ``.meta.json`` sidecar includes the complete source STAC item,
        asset metadata, requested/actual bounds and the output SHA-256. The
        checksum identifies this derived crop, not the original full tile.
        A GeoTIFF internal mask is used when all band masks agree. Distinct
        band masks are retained through a shared nodata value when possible;
        unsupported mask combinations raise rather than discard information.
        """
        rio = _rasterio()
        transform_module = importlib.import_module("rasterio.transform")
        path = Path(destination)
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        stale_mask = Path(str(path) + ".msk")
        if not overwrite and any(candidate.exists() for candidate in (path, sidecar, stale_mask)):
            raise FileExistsError(
                f"Output already exists: {path}; set overwrite=True to replace it"
            )
        if len(self.nodata_values) != self.data.shape[0] or not _same_nodata(self.nodata_values):
            raise ValueError(
                "A GeoTIFF needs the same nodata value across bands; save assets separately"
            )
        nodata = self.nodata_values[0]
        masks = np.ma.getmaskarray(self.data)
        common_mask = bool(np.all(masks == masks[0]))
        if not common_mask:
            if nodata is None:
                raise ValueError(
                    "Cannot preserve distinct band masks without a shared nodata value"
                )
            value_mask = (
                np.isnan(self.data.data) if math.isnan(nodata) else self.data.data == nodata
            )
            if not np.array_equal(masks, value_mask):
                raise ValueError(
                    "Cannot encode these distinct band masks losslessly in one GeoTIFF"
                )

        count, height, width = self.data.shape
        profile = {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "count": count,
            "dtype": self.data.dtype,
            "crs": self.crs,
            "transform": transform_module.Affine(*self.transform),
            "nodata": nodata,
            "compress": "deflate",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, suffix=".tif", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            with (
                rio.Env(GDAL_TIFF_INTERNAL_MASK=True),
                rio.open(temporary_path, "w", **profile) as dst,
            ):
                dst.write(self.data.data)
                if common_mask:
                    dst.write_mask(~masks[0])
                if "reflectance" in self.asset_metadata.get("roles", []):
                    scales, offsets = _band_calibration(self.asset_metadata, count)
                    dst.scales = tuple(scales)
                    dst.offsets = tuple(offsets)
                dst.update_tags(
                    source_url=self.source_url,
                    scene_id=self.scene_id,
                    asset_key=self.asset_key,
                    pixel_values="raw; scale and offset have not been applied",
                )
            with temporary_path.open("rb") as stream:
                digest = file_digest(stream, "sha256").hexdigest()
            size = temporary_path.stat().st_size
            provenance = {
                "source": "Earth Search ground image crop",
                "url": self.source_url,
                "retrieved_at": self.retrieved_at,
                "saved_at": datetime.now(UTC).isoformat(),
                "sha256": digest,
                "bytes": size,
                "path": str(path),
                "scene_id": self.scene_id,
                "asset_key": self.asset_key,
                "bbox_wgs84": list(self.bbox_wgs84),
                "bounds": list(self.bounds),
                "crs": self.crs,
                "transform": list(self.transform),
                "shape": list(self.data.shape),
                "dtype": str(self.data.dtype),
                "nodata_values": [
                    "NaN" if value is not None and math.isnan(value) else value
                    for value in self.nodata_values
                ],
                "scale_offset_applied": False,
                "cloud_mask_applied": False,
                "resampling": "none; native pixel-aligned window",
                "asset": self.asset_metadata,
                "stac_item": self.item_metadata,
            }
            # Serialize before replacing an existing output: malformed user-
            # supplied metadata must not destroy a previously valid crop.
            metadata_text = json.dumps(provenance, indent=2, allow_nan=False) + "\n"
            os.replace(temporary_path, path)
            if stale_mask.exists():
                stale_mask.unlink()
            sidecar.write_text(metadata_text, encoding="utf-8")
        finally:
            temporary_path.unlink(missing_ok=True)
        return DownloadReceipt(
            source="Earth Search ground image crop",
            url=self.source_url,
            retrieved_at=self.retrieved_at,
            sha256=digest,
            bytes=size,
            path=str(path),
        )


def read_ground_image(
    item: dict[str, Any],
    *,
    bbox: tuple[float, float, float, float],
    asset: str = "visual",
    max_pixels: int = 4_000_000,
) -> GroundImage:
    """Read a WGS84 area from one HTTPS GeoTIFF asset at native resolution.

    ``bbox`` is ``(west, south, east, north)`` in longitude/latitude degrees.
    The crop covers the transformed bounding rectangle, rounded outward to
    source pixels; it is not an exact polygon clip. The selected tile must
    cover the entire crop. Select another tile or mosaic explicitly when
    an area crosses a tile edge.

    ``max_pixels`` limits the total band samples (bands * rows * columns)
    before pixel data are read. COG range reads retrieve the intersecting
    compressed blocks, which can be larger than the requested pixel window.
    Different assets retain their native grids (e.g. RGB 10 m, SCL 20 m).
    No reprojection, resampling, reflectance scaling or cloud mask occurs.
    """
    bounds_wgs84 = _validate_bbox(bbox)
    if isinstance(max_pixels, bool) or not isinstance(max_pixels, int) or max_pixels <= 0:
        raise ValueError("max_pixels must be a positive integer")
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise ValueError("A STAC item with a string id is required")
    assets = item.get("assets")
    if not isinstance(assets, dict) or asset not in assets:
        raise ValueError(f"STAC item has no {asset!r} asset")
    metadata = assets[asset]
    if not isinstance(metadata, dict) or not isinstance(metadata.get("href"), str):
        raise ValueError("The selected asset needs an HTTPS href")
    href = metadata["href"]
    parsed = urlsplit(href)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Ground imagery assets must use public HTTPS URLs without credentials")
    media_type = metadata.get("type", "")
    if not isinstance(media_type, str) or "image/tiff" not in media_type.lower():
        raise ValueError(
            "Select a GeoTIFF/COG asset; JPEG previews and metadata are not image grids"
        )

    rio = _rasterio()
    warp = importlib.import_module("rasterio.warp")
    windows = importlib.import_module("rasterio.windows")
    with (
        rio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            GDAL_HTTP_TIMEOUT="30",
            GDAL_HTTP_MAX_RETRY="2",
            GDAL_HTTP_RETRY_DELAY="1",
        ),
        rio.open(href) as src,
    ):
        if src.crs is None:
            raise ValueError("Ground imagery asset has no coordinate reference system")
        if (
            src.transform.b != 0
            or src.transform.d != 0
            or src.transform.a <= 0
            or src.transform.e >= 0
        ):
            raise ValueError("Only north-up GeoTIFF grids are supported")
        projected = warp.transform_bounds("EPSG:4326", src.crs, *bounds_wgs84, densify_pts=21)
        if not all(math.isfinite(value) for value in projected):
            raise ValueError("The requested bbox cannot be projected into this image grid")
        fractional = windows.from_bounds(*projected, transform=src.transform)
        # Floating-point transforms can put an exact pixel edge a few ulps
        # across its integer index. Round only that numerical noise away.
        col_start = math.floor(round(fractional.col_off, 8))
        row_start = math.floor(round(fractional.row_off, 8))
        col_stop = math.ceil(round(fractional.col_off + fractional.width, 8))
        row_stop = math.ceil(round(fractional.row_off + fractional.height, 8))
        if col_stop <= 0 or row_stop <= 0 or col_start >= src.width or row_start >= src.height:
            raise ValueError("The requested bbox does not intersect the selected image")
        if col_start < 0 or row_start < 0 or col_stop > src.width or row_stop > src.height:
            raise ValueError(
                "The selected image does not cover the entire bbox; select another scene "
                "or mosaic the intersecting tiles explicitly"
            )
        width, height = col_stop - col_start, row_stop - row_start
        sample_count = int(src.count) * width * height
        if width <= 0 or height <= 0:
            raise ValueError("The requested bbox produces an empty image window")
        if sample_count > max_pixels:
            raise ValueError(
                f"Crop requires {sample_count:,} band samples, above max_pixels={max_pixels:,}; "
                "use a smaller bbox or explicitly raise the limit"
            )
        window = windows.Window.from_slices((row_start, row_stop), (col_start, col_stop))
        data = src.read(window=window, masked=True)
        affine = src.window_transform(window)
        left, bottom, right, top = windows.bounds(window, src.transform)
        image = GroundImage(
            data=data,
            crs=src.crs.to_string(),
            transform=(affine.a, affine.b, affine.c, affine.d, affine.e, affine.f),
            bounds=(float(left), float(bottom), float(right), float(top)),
            scene_id=item["id"],
            asset_key=asset,
            source_url=href,
            asset_metadata=deepcopy(metadata),
            bbox_wgs84=bounds_wgs84,
            item_metadata=deepcopy(item),
            nodata_values=tuple(src.nodatavals),
            retrieved_at=datetime.now(UTC).isoformat(),
        )
    return image
