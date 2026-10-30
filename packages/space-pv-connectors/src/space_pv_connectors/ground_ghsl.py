"""Native GHSL settlement classes for terrestrial PV inventory context.

The paper's urban categories are codes 21, 22, 23 and 30; water is code 10.
R2023A is a newer processing edition, even when its epoch is 2015. It is not
the historical R2019A input used by Dunnett et al. (2020). A local R2019A
raster can be supplied explicitly; editions are never substituted silently.

Sources: https://doi.org/10.1038/s41597-020-0469-8 and the JRC GHSL manuals,
https://human-settlement.emergency.copernicus.eu/documents/GHSL_Data_Package_2019.pdf
and https://human-settlement.emergency.copernicus.eu/ghs_smod2023.php.
"""

from __future__ import annotations

import importlib
import json
import math
import zipfile
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import file_digest
from numbers import Real
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from .ground_osm import _atomic_write
from .ground_raster import _rasterio, _validate_bbox
from .http_base import HttpConnector

_BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
_CRS = "ESRI:54009"
_CLASSES = {
    10: "water",
    11: "very low density rural",
    12: "low density rural",
    13: "rural cluster",
    21: "suburban or peri-urban",
    22: "semi-dense urban cluster",
    23: "dense urban cluster",
    30: "urban centre",
}
_URBAN = frozenset({21, 22, 23, 30})
_RASTER_OPTIONS = {"GDAL_PAM_ENABLED": False, "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"}


def _positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _metadata(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(path.suffix + ".meta.json")
    if not sidecar.is_file():
        raise ValueError(f"GHSL cache has no provenance sidecar: {sidecar}")
    try:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("GHSL cache provenance is not valid JSON") from exc
    if not isinstance(metadata, dict):
        raise ValueError("GHSL cache provenance must be an object")
    if metadata.get("sha256") != _digest(path) or metadata.get("bytes") != path.stat().st_size:
        raise ValueError("GHSL cache checksum or size does not match its provenance")
    return metadata


def _product(edition: str, epoch: int) -> tuple[str, str]:
    if isinstance(epoch, bool) or not isinstance(epoch, int):
        raise ValueError("epoch must be an integer GHSL reference year")
    if edition == "R2023A" and epoch in range(1975, 2031, 5):
        product = f"GHS_SMOD_E{epoch}_GLOBE_R2023A_54009_1000"
        return product + "_V2_0", f"{_BASE}/GHS_SMOD_GLOBE_R2023A/{product}/V2-0/{product}_V2_0.zip"
    if edition == "R2019A" and epoch in (1975, 1990, 2000, 2015):
        product = f"GHS_SMOD_POP{epoch}_GLOBE_R2019A_54009_1K"
        return product + "_V2_0", f"{_BASE}/GHS_SMOD_POP_GLOBE_R2019A/{product}/{product}_V2_0.zip"
    raise ValueError("Use R2023A epochs 1975-2030 in 5-year steps, or R2019A 1975/1990/2000/2015")


def _native_grid(dataset: Any) -> None:
    rio = _rasterio()
    transform = dataset.transform
    if (
        dataset.driver != "GTiff"
        or dataset.count != 1
        or dataset.crs != rio.crs.CRS.from_string(_CRS)
        or not np.issubdtype(np.dtype(dataset.dtypes[0]), np.integer)
        or not all(math.isfinite(value) for value in tuple(transform)[:6])
        or not math.isclose(transform.a, 1000.0, rel_tol=0, abs_tol=1e-6)
        or not math.isclose(transform.e, -1000.0, rel_tol=0, abs_tol=1e-6)
        or transform.b != 0
        or transform.d != 0
    ):
        raise ValueError(
            "GHSL requires a single integer band on the native north-up 1 km Mollweide grid"
        )


@dataclass(frozen=True, slots=True)
class SettlementRaster:
    """A native 1 km categorical GHSL crop and its source provenance.

    ``data`` is a two-dimensional masked integer array. These classes describe
    settlement context at ``epoch``; they do not describe current PV land use
    or validate an individual rooftop, ground-mounted plant or water boundary.
    The original grid is retained, unlike the paper's Eckert IV reprojection.
    """

    data: np.ma.MaskedArray
    crs: str
    transform: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]
    bbox_wgs84: tuple[float, float, float, float]
    epoch: int
    edition: str
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Check public instances as well as connector-created crops."""
        if (
            not isinstance(self.data, np.ma.MaskedArray)
            or self.data.ndim != 2
            or 0 in self.data.shape
            or self.data.dtype.kind not in "iu"
        ):
            raise ValueError(
                "Settlement data must be a nonempty two-dimensional masked integer array"
            )
        mask = np.ma.getmaskarray(self.data)
        if mask.shape != self.data.shape or mask.dtype != np.dtype(bool):
            raise ValueError("Settlement mask must be boolean and match the data shape")
        for values, length, name in ((self.transform, 6, "transform"), (self.bounds, 4, "bounds")):
            if (
                not isinstance(values, (tuple, list))
                or len(values) != length
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, Real)
                    or not math.isfinite(value)
                    for value in values
                )
            ):
                raise ValueError(
                    f"Settlement {name} must contain {length} finite numeric coordinates"
                )
        a, b, c, d, e, f = self.transform
        rio = _rasterio()
        try:
            crs = rio.crs.CRS.from_user_input(self.crs)
        except (ValueError, TypeError) as exc:
            raise ValueError("Settlement CRS must identify World Mollweide (ESRI:54009)") from exc
        if (
            crs != rio.crs.CRS.from_string(_CRS)
            or not math.isclose(a, 1000, rel_tol=0, abs_tol=1e-6)
            or not math.isclose(e, -1000, rel_tol=0, abs_tol=1e-6)
            or b != 0
            or d != 0
        ):
            raise ValueError("Settlement data must use the native north-up 1 km Mollweide grid")
        height, width = self.data.shape
        if not np.allclose(self.bounds, (c, f + height * e, c + width * a, f), rtol=0, atol=1e-6):
            raise ValueError("Settlement bounds disagree with the transform and data shape")
        _validate_bbox(self.bbox_wgs84)
        _product(self.edition, self.epoch)
        if not isinstance(self.provenance, dict):
            raise ValueError("Settlement provenance must be a JSON object")
        try:
            json.dumps(self.provenance, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Settlement provenance must contain finite JSON-compatible values"
            ) from exc

    def sample_points(self, lon_lat: Sequence[Sequence[float]]) -> list[dict[str, Any]]:
        """Sample WGS84 points without interpolation; unknown flags are None.

        Supplying farm centroids implements a clearly defined centroid lookup.
        It does not calculate the fraction of an entire farm covered by water
        or urban cells. Outside-crop, masked and unknown-code results remain
        explicit rather than being counted as rural/non-water observations.
        """
        self._validate()
        points = np.asarray(lon_lat, dtype=float)
        if points.size == 0:
            return []
        if (
            points.ndim != 2
            or points.shape[1] != 2
            or not np.isfinite(points).all()
            or np.any(np.abs(points[:, 0]) > 180)
            or np.any(np.abs(points[:, 1]) > 90)
        ):
            raise ValueError("lon_lat must contain finite WGS84 (longitude, latitude) pairs")
        warp = importlib.import_module("rasterio.warp")
        xs, ys = warp.transform("EPSG:4326", self.crs, points[:, 0], points[:, 1])
        a, _, c, _, e, f = self.transform
        mask = np.ma.getmaskarray(self.data)
        records = []
        for (lon, lat), x, y in zip(points, xs, ys, strict=True):
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("The requested point cannot be projected into the GHSL grid")
            row, col = math.floor((y - f) / e), math.floor((x - c) / a)
            status = "outside_crop"
            code = None
            if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
                if mask[row, col]:
                    status = "nodata"
                else:
                    code = int(self.data.data[row, col])
                    status = "valid" if code in _CLASSES else "unknown_class"
            valid = status == "valid"
            records.append(
                {
                    "longitude": float(lon),
                    "latitude": float(lat),
                    "class_code": code,
                    "settlement_class": _CLASSES.get(code, "unknown"),
                    "urban": code in _URBAN if valid else None,
                    "water": code == 10 if valid else None,
                    "status": status,
                    "epoch": self.epoch,
                    "edition": self.edition,
                    "sampling": "native cell containing point",
                }
            )
        return records

    def save(self, destination: str | Path, *, overwrite: bool = False) -> None:
        """Write raw classes and internal nodata mask with a SHA-256 sidecar."""
        self._validate()
        rio = _rasterio()
        affine = importlib.import_module("rasterio.transform").Affine
        path = Path(destination)
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        if not overwrite and (path.exists() or sidecar.exists()):
            raise FileExistsError(f"GHSL output already exists: {path}")
        if any(Path(str(path) + suffix).exists() for suffix in (".msk", ".aux.xml")):
            raise ValueError("GHSL output has an external mask or auxiliary file")
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, suffix=".tif", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with (
                rio.Env(GDAL_TIFF_INTERNAL_MASK=True, **_RASTER_OPTIONS),
                rio.open(
                    temporary,
                    "w",
                    driver="GTiff",
                    count=1,
                    width=self.data.shape[1],
                    height=self.data.shape[0],
                    dtype=self.data.dtype,
                    crs=self.crs,
                    transform=affine(*self.transform),
                    compress="deflate",
                ) as dst,
            ):
                dst.write(self.data.data, 1)
                dst.write_mask(~np.ma.getmaskarray(self.data))
                dst.update_tags(product="GHS-SMOD", edition=self.edition, epoch=self.epoch)
            metadata = {
                "schema": "orbitalpv-ghsl-crop-v1",
                "sha256": _digest(temporary),
                "bytes": temporary.stat().st_size,
                "edition": self.edition,
                "epoch": self.epoch,
                "shape": list(self.data.shape),
                "dtype": str(self.data.dtype),
                "crs": self.crs,
                "transform": list(self.transform),
                "bounds": list(self.bounds),
                "bbox_wgs84": list(self.bbox_wgs84),
                "resampled": False,
                "provenance": deepcopy(self.provenance),
            }
            temporary.replace(path)
            _atomic_write(sidecar, (json.dumps(metadata, indent=2) + "\n").encode())
        finally:
            temporary.unlink(missing_ok=True)


def load_settlement_raster(path: str | Path, *, max_pixels: int = 1_000_000) -> SettlementRaster:
    """Restore and verify a saved GHSL crop entirely offline."""
    _positive_int(max_pixels, "max_pixels")
    path = Path(path)
    if any(Path(str(path) + suffix).exists() for suffix in (".msk", ".aux.xml")):
        raise ValueError("GHSL crops cannot use unverified external masks or auxiliary files")
    meta = _metadata(path)
    if meta.get("schema") != "orbitalpv-ghsl-crop-v1" or meta.get("resampled") is not False:
        raise ValueError("GHSL cache is not a native OrbitalPV settlement crop")
    edition, epoch = meta.get("edition"), meta.get("epoch")
    if not isinstance(edition, str) or not isinstance(epoch, int):
        raise ValueError("GHSL crop must declare its edition and epoch")
    _product(edition, epoch)
    bbox = _validate_bbox(meta.get("bbox_wgs84", ()))
    if not isinstance(meta.get("provenance"), dict):
        raise ValueError("GHSL crop must retain source provenance")
    rio = _rasterio()
    with rio.Env(**_RASTER_OPTIONS), rio.open(path) as src:
        _native_grid(src)
        if src.width * src.height > max_pixels:
            raise ValueError("GHSL crop exceeds max_pixels")
        if (
            meta.get("shape") != [src.height, src.width]
            or meta.get("dtype") != src.dtypes[0]
            or rio.crs.CRS.from_user_input(meta.get("crs")) != src.crs
            or meta.get("transform") != list(src.transform)[:6]
            or meta.get("bounds") != list(src.bounds)
            or src.tags().get("edition") != meta["edition"]
            or src.tags().get("epoch") != str(meta["epoch"])
        ):
            raise ValueError("GHSL crop metadata does not match its native raster")
        data = src.read(1, masked=True)
    return SettlementRaster(
        data,
        meta["crs"],
        tuple(meta["transform"]),
        tuple(meta["bounds"]),
        bbox,
        meta["epoch"],
        meta["edition"],
        deepcopy(meta["provenance"]),
    )


class GHSLSettlementConnector(HttpConnector):
    """Retrieve JRC GHS-SMOD context while preserving its edition and epoch.

    The official R2023A V2.0 global ZIP is downloaded once and reused; the
    2015 archive is about 29 MB. Only a bounded native-resolution window is
    read into memory. The ZIP size is capped before and during downloading,
    and its member is validated before Rasterio opens it.

    Original R2019A downloads are no longer served at the official URL as of
    October 2026. Use ``edition='R2019A', source_path=...`` with a retained
    native historical GeoTIFF. No fallback to a different edition occurs.
    """

    def fetch_settlement(
        self,
        *,
        bbox: Sequence[float],
        cache_path: str | Path,
        source_cache_dir: str | Path | None = None,
        source_path: str | Path | None = None,
        edition: str = "R2023A",
        epoch: int = 2015,
        refresh: bool = False,
        offline: bool = False,
        max_download_bytes: int = 64 * 1024 * 1024,
        max_pixels: int = 1_000_000,
    ) -> SettlementRaster:
        """Return a native crop for WGS84 ``(west, south, east, north)``.

        ``offline`` permits an existing validated crop or local source, and
        prevents HTTP calls. ``refresh`` replaces a crop from the same source;
        archived versioned source files remain cached. A local ``source_path``
        is hashed and its edition/epoch are caller declarations recorded in
        provenance; filenames alone cannot verify those declarations.
        """
        if len(bbox) != 4:
            raise ValueError("bbox must contain (west, south, east, north)")
        bounds = _validate_bbox((bbox[0], bbox[1], bbox[2], bbox[3]))
        product, url = _product(edition, epoch)
        _positive_int(max_pixels, "max_pixels")
        _positive_int(max_download_bytes, "max_download_bytes")
        if not isinstance(refresh, bool) or not isinstance(offline, bool):
            raise ValueError("refresh and offline must be booleans")
        if refresh and offline:
            raise ValueError("offline=True cannot be combined with refresh=True")
        path = Path(cache_path)
        source = Path(source_path) if source_path is not None else None
        request = {
            "bbox": list(bounds),
            "edition": edition,
            "epoch": epoch,
            "version": "2.0",
            "source_url": url if source is None else None,
            "local_source_sha256": _digest(source) if source is not None else None,
        }
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        if not refresh and (path.exists() != sidecar.exists()):
            raise ValueError("GHSL cache has an incomplete raster/sidecar pair; use refresh=True")
        if path.is_file() and not refresh:
            result = load_settlement_raster(path, max_pixels=max_pixels)
            if result.provenance.get("request") != request:
                raise ValueError("GHSL cache belongs to a different request; use a new cache_path")
            return result
        if source is None:
            if edition == "R2019A":
                raise FileNotFoundError(
                    "Historical R2019A requires a retained local source_path; no edition fallback is used"
                )
            directory = Path(source_cache_dir) if source_cache_dir else path.parent / "ghsl_source"
            archive = directory / f"{product}.zip"
            source_meta = self._archive(archive, url, offline=offline, max_bytes=max_download_bytes)
            with zipfile.ZipFile(archive) as zipped:
                members = [
                    member for member in zipped.infolist() if member.filename == product + ".tif"
                ]
                if (
                    len(members) != 1
                    or members[0].is_dir()
                    or members[0].file_size > 256 * 1024 * 1024
                ):
                    raise ValueError(
                        "GHSL archive must contain exactly one bounded expected GeoTIFF"
                    )
            raster_path = f"/vsizip/{archive.resolve()}/{product}.tif"
            source_info = {
                "url": url,
                "archive_sha256": source_meta["sha256"],
                "archive_bytes": source_meta["bytes"],
                "member": product + ".tif",
            }
        else:
            raster_path = str(source)
            source_info = {
                "local_source": source.name,
                "source_sha256": request["local_source_sha256"],
                "edition_epoch_declared_by_caller": True,
            }
        rio = _rasterio()
        windows = importlib.import_module("rasterio.windows")
        warp = importlib.import_module("rasterio.warp")
        with rio.Env(**_RASTER_OPTIONS), rio.open(raster_path) as src:
            _native_grid(src)
            projected = warp.transform_bounds("EPSG:4326", src.crs, *bounds, densify_pts=21)
            if not all(math.isfinite(value) for value in projected):
                raise ValueError("The requested bbox cannot be projected into the GHSL grid")
            window = windows.from_bounds(*projected, transform=src.transform)
            row0, col0 = math.floor(window.row_off), math.floor(window.col_off)
            row1, col1 = (
                math.ceil(window.row_off + window.height),
                math.ceil(window.col_off + window.width),
            )
            if row0 < 0 or col0 < 0 or row1 > src.height or col1 > src.width:
                raise ValueError("The complete requested bbox must fit within the GHSL raster")
            if (row1 - row0) * (col1 - col0) > max_pixels:
                raise ValueError("GHSL request exceeds max_pixels; use a smaller bbox")
            selected = windows.Window.from_slices((row0, row1), (col0, col1))
            data = src.read(1, window=selected, masked=True)
            result = SettlementRaster(
                data=data,
                crs=src.crs.to_string(),
                transform=tuple(src.window_transform(selected))[:6],
                bounds=tuple(windows.bounds(selected, src.transform)),
                bbox_wgs84=bounds,
                epoch=epoch,
                edition=edition,
                provenance={
                    "request": request,
                    "source": "European Commission JRC GHS-SMOD",
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "product": product,
                    **source_info,
                    "license": "CC-BY-4.0",
                    "attribution": "© European Union, JRC GHSL",
                    "resampling": "none; native 1 km Mollweide grid",
                    "paper_input_edition": edition == "R2019A" and epoch == 2015,
                    "historical_epoch_not_current_land_cover": epoch < datetime.now(UTC).year,
                },
            )
        result.save(path, overwrite=refresh)
        return result

    def _archive(self, path: Path, url: str, *, offline: bool, max_bytes: int) -> dict[str, Any]:
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        if path.exists() != sidecar.exists():
            raise ValueError("GHSL source archive has an incomplete provenance pair")
        if path.is_file():
            if path.stat().st_size > max_bytes:
                raise ValueError("Cached GHSL archive exceeds max_download_bytes")
            meta = _metadata(path)
            if meta.get("url") != url:
                raise ValueError("GHSL source archive belongs to a different URL")
            return meta
        if offline:
            raise FileNotFoundError(
                "No cached GHSL source archive; offline=True prevents downloading"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, suffix=".zip", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with self._client.stream("GET", url) as response:
                response.raise_for_status()
                length = response.headers.get("content-length")
                if length is not None and (not length.isdigit() or int(length) > max_bytes):
                    raise ValueError(
                        "GHSL download exceeds max_download_bytes or has an invalid length"
                    )
                size = 0
                with temporary.open("wb") as target:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("GHSL download exceeds max_download_bytes")
                        target.write(chunk)
                if not zipfile.is_zipfile(temporary):
                    raise ValueError("GHSL download is not a ZIP archive")
                meta = {
                    "url": url,
                    "final_url": str(response.url),
                    "sha256": _digest(temporary),
                    "bytes": size,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                }
            temporary.replace(path)
            _atomic_write(sidecar, (json.dumps(meta, indent=2) + "\n").encode())
            return meta
        finally:
            temporary.unlink(missing_ok=True)
