"""Anonymous NASA lunar inputs with bounded downloads and checked local caches.

LOLA is measured/interpolated terrain, Diviner is binned radiometry, SPICE and
SVS are computed geometry. None of these sources measures photovoltaic power.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd

from space_pv_space_env.lunar import MOON_RADIUS_M, LunarTerrain

from .http_base import DownloadReceipt
from .research_http import ResearchConnector, ResearchResponse, bounded_int, require_fields


class _LunarDownload(ResearchConnector):
    def _cached_download(self, url, destination, *, refresh=False, max_bytes=300_000_000):
        path = Path(destination)
        if path.exists() and not refresh:
            sidecar = path.with_name(path.name + ".provenance.json")
            if not sidecar.exists():
                raise ValueError("Existing data has no provenance; use refresh=True")
            receipt = json.loads(sidecar.read_text())
            if receipt.get("request_url") != url or receipt.get("source") != self.SOURCE:
                raise ValueError("Cache belongs to a different product")
            if hashlib.sha256(path.read_bytes()).hexdigest() != receipt.get("sha256"):
                raise ValueError("Cached data checksum mismatch")
            return DownloadReceipt(**{k: receipt[k] for k in DownloadReceipt.__dataclass_fields__})
        return self._download(url, path, max_bytes=max_bytes)


class LolaConnector(_LunarDownload):
    """NASA PGDA LOLA DEMs; native metres, lunar south-polar stereographic.

    The broad 80 m product is about 189 MB. Five-metre site products have
    interpolated pixels; nominal grid spacing is not measurement resolution.
    The same site API also retrieves published height-uncertainty rasters.
    """

    SOURCE = "NASA PGDA LOLA"
    DOCUMENTATION = "https://pgda.gsfc.nasa.gov/products/90"

    def polar_dem(self, destination: str | Path, *, refresh: bool = False) -> DownloadReceipt:
        """Download the 80--90 south, 80 m DEM in MOON_ME_DE421."""
        return self._cached_download(
            "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF",
            destination,
            refresh=refresh,
        )

    def site_dem(
        self,
        site: str,
        destination: str | Path,
        *,
        height_error: bool = False,
        refresh: bool = False,
    ) -> DownloadReceipt:
        """Download published 5 m site terrain or total Z uncertainty (metres).

        Supported sites are 01, 04 and 11 from PGDA product 78. The uncertainty
        product is not itself a terrain DEM and must not be used as elevation.
        """
        if site not in {"01", "04", "11"}:
            raise ValueError("Supported site IDs: 01, 04, 11")
        suffix = "toterr" if height_error else "surf"
        return self._cached_download(
            f"https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site{site}/Site{site}_final_adj_5mpp_{suffix}.tif",
            destination,
            refresh=refresh,
        )


def read_lola_geotiff(
    path: str | Path, *, bounds_m: tuple[float, float, float, float] | None = None, stride: int = 1
) -> LunarTerrain:
    """Read an explicit window, retaining pixel centres and missing cells.

    ``bounds_m`` is (left,bottom,right,top), in projected lunar metres. Optional
    integer stride samples native pixels without smoothing; it can miss peaks.
    Requires the ``ground`` extra (rasterio). Verify the product is elevation,
    not a height-error, count or hillshade map, before calling this function.
    """
    import rasterio
    from rasterio.windows import from_bounds

    bounded_int(stride, "stride", 1, 10_000)
    with rasterio.open(path) as source:
        crs = source.crs.to_dict() if source.crs else {}
        # CRS names vary between PGDA releases; test numeric projection parameters.
        radius = crs.get("R", crs.get("a", 0))
        if (
            crs.get("proj") != "stere"
            or crs.get("lat_0") != -90
            or crs.get("lat_ts", -90) != -90
            or crs.get("lon_0", 0) != 0
            or abs(radius - MOON_RADIUS_M) > 0.01
        ):
            raise ValueError("Require lunar south-polar stereographic CRS, R=1737400 m")
        if (
            crs.get("units") != "m"
            or crs.get("x_0", 0) != 0
            or crs.get("y_0", 0) != 0
            or crs.get("k", 1) != 1
        ):
            raise ValueError("Unsupported projection units, offsets or scale")
        if (
            source.count != 1
            or source.transform.b != 0
            or source.transform.d != 0
            or source.scales != (1.0,)
            or source.offsets != (0.0,)
        ):
            raise ValueError("Require an unrotated single-band raster")
        window = from_bounds(*source.bounds, transform=source.transform)
        if bounds_m is not None:
            if len(bounds_m) != 4 or not np.isfinite(bounds_m).all():
                raise ValueError("Require finite (left,bottom,right,top) bounds")
            left, bottom, right, top = bounds_m
            if (
                left >= right
                or bottom >= top
                or left < source.bounds.left
                or right > source.bounds.right
                or bottom < source.bounds.bottom
                or top > source.bounds.top
            ):
                raise ValueError("Requested bounds are invalid or outside the raster")
            window = (
                from_bounds(*bounds_m, transform=source.transform).round_offsets().round_lengths()
            )
        array = (
            source.read(1, window=window, masked=True)
            .astype(float)
            .filled(np.nan)[::stride, ::stride]
        )
        transform = source.window_transform(window)
        x = transform.c + (np.arange(array.shape[1]) * stride + 0.5) * transform.a
        y = transform.f + (np.arange(array.shape[0]) * stride + 0.5) * transform.e
        if x[0] > x[-1]:
            x, array = x[::-1], array[:, ::-1]
        if y[0] > y[-1]:
            y, array = y[::-1], array[::-1]
    return LunarTerrain(x, y, array)


class DivinerConnector(_LunarDownload):
    """PDS4 Diviner south-pole seasonal PCP bolometric temperature tables.

    This explicit product family bins 2009--2020 observations at 240 m in
    L_s=0--60 degrees and one of 24 subsolar-longitude bins, 15 degrees wide.
    It is a cumulative climatology, not a dated 2026 weather/temperature series.
    Empty bins are absent. Original TAB and XML labels are both retained.
    """

    SOURCE = "NASA PDS LRO Diviner PCP"
    DOCUMENTATION = "https://pds-geosciences.wustl.edu/missions/lro/diviner.htm"
    BASE = "https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_pcp/seasonal/slon/pols"

    def seasonal_temperature(
        self, subsolar_bin: int, directory: str | Path, *, refresh: bool = False
    ) -> tuple[DownloadReceipt, DownloadReceipt]:
        """Download a 15-degree bin (1..24), about 200 MB, with its PDS4 label."""
        bounded_int(subsolar_bin, "subsolar_bin", 1, 24)
        stem = f"pcp_avg_tbol_pols_ls030_slon{subsolar_bin:02d}_240"
        directory = Path(directory)
        label = self._cached_download(
            f"{self.BASE}/{stem}.xml",
            directory / f"{stem}.xml",
            refresh=refresh,
            max_bytes=1_000_000,
        )
        data = self._cached_download(
            f"{self.BASE}/{stem}.tab", directory / f"{stem}.tab", refresh=refresh
        )
        return data, label


def parse_diviner_pcp(content: bytes, label: bytes, *, allow_subset: bool = False) -> pd.DataFrame:
    """Parse the labelled six-column PCP family; preserve missing values as NaN.

    Labels incorrectly assign degrees to normalized x/y; the field descriptions
    specify normalization by lunar radius. Output x_m/y_m follows that
    description and is checked against the published longitude/latitude. The
    original normalized coordinates are retained. ``allow_subset`` is only for
    byte-preserving subsets with separately recorded extraction provenance.
    """
    root = ET.fromstring(label)
    ns = {"p": "http://pds.nasa.gov/pds4/pds/v1"}
    table = root.find(".//p:Table_Character", ns)
    if table is None:
        raise ValueError("No PDS4 character table")
    fields = table.findall(".//p:Field_Character", ns)
    names = [field.findtext("p:name", namespaces=ns) for field in fields]
    if names != ["x", "y", "clon", "clat", "ltim", "tbol"]:
        raise ValueError("Unsupported Diviner PCP columns")
    if fields[-1].findtext("p:unit", namespaces=ns) != "K":
        raise ValueError("Temperature label must specify Kelvin")
    offset = int(table.findtext("p:offset", namespaces=ns) or "0")
    rows = content[offset:].splitlines()
    expected = int(table.findtext("p:records", namespaces=ns) or "0")
    if (not allow_subset and len(rows) != expected) or not rows:
        raise ValueError("Diviner record count does not match its label")
    colspecs = []
    for field in fields:
        start = int(field.findtext("p:field_location", namespaces=ns) or "0") - 1
        size = int(field.findtext("p:field_length", namespaces=ns) or "0")
        colspecs.append((start, start + size))
    if any(len(row) < colspecs[-1][1] for row in rows):
        raise ValueError("Truncated Diviner row")
    frame = pd.read_fwf(
        io.StringIO(content[offset:].decode("ascii")), colspecs=colspecs, names=names, dtype=float
    )
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Malformed numeric Diviner data")
    for field, name in zip(fields, names, strict=True):
        for special in field.findall("p:Special_Constants/*", ns):
            frame[name] = frame[name].mask(frame[name] == float(special.text or "nan"))
    frame = frame.rename(
        columns={
            "x": "x_normalized",
            "y": "y_normalized",
            "clon": "longitude_deg",
            "clat": "latitude_deg",
            "ltim": "local_time_h",
            "tbol": "temperature_k",
        }
    )
    frame["x_m"] = frame.x_normalized * MOON_RADIUS_M
    frame["y_m"] = frame.y_normalized * MOON_RADIUS_M
    if (
        np.any(frame.temperature_k <= 0)
        or np.any(np.abs(frame.latitude_deg) > 90)
        or np.any(np.abs(frame.longitude_deg) > 360)
        or np.any((frame.local_time_h < 0) | (frame.local_time_h > 24))
    ):
        raise ValueError("Invalid Diviner physical values")
    # Also detect a projection-orientation mismatch instead of misplacing data.
    lon, lat = np.deg2rad(frame.longitude_deg), np.deg2rad(frame.latitude_deg)
    radius = 2 * MOON_RADIUS_M * np.tan((np.pi / 2 + lat) / 2)
    error = np.hypot(frame.x_m - radius * np.sin(lon), frame.y_m - radius * np.cos(lon))
    if np.any(error > 5):
        raise ValueError("Diviner coordinates disagree with lunar polar projection")
    frame.attrs.update(
        logical_identifier=root.findtext(".//p:logical_identifier", namespaces=ns),
        description=table.findtext("p:description", namespaces=ns),
        original_records=expected,
        subset=allow_subset,
        data_kind="binned measured bolometric brightness temperature; not cell temperature",
    )
    return frame


class LunarSpiceConnector(_LunarDownload):
    """Pinned DE421 kernel set matching LOLA's MOON_ME_DE421 frame.

    Downloading does not load or clear SPICE's global pool. The leap-second
    kernel is a fixed version; UTC dates beyond its last leap require checking
    for subsequent leap seconds before operational use. Coverage is bounded by
    the kernels (lunar orientation 1900--2050), with errors propagated by SPICE.
    """

    SOURCE = "NASA NAIF lunar DE421 kernels"
    DOCUMENTATION = (
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf"
    )
    KERNELS: ClassVar[dict[str, str]] = {
        "naif0012.tls": "lsk/naif0012.tls",
        "de421.bsp": "spk/planets/a_old_versions/de421.bsp",
        "moon_pa_de421_1900-2050.bpc": "pck/moon_pa_de421_1900-2050.bpc",
        "moon_080317.tf": "fk/satellites/moon_080317.tf",
    }

    def download(self, directory: str | Path, *, refresh: bool = False) -> list[DownloadReceipt]:
        """Retrieve all four named kernels; checked caches support offline reuse."""
        return [
            self._cached_download(
                f"https://naif.jpl.nasa.gov/pub/naif/generic_kernels/{relative}",
                Path(directory) / name,
                refresh=refresh,
                max_bytes=25_000_000,
            )
            for name, relative in self.KERNELS.items()
        ]


class LunarIlluminationConnector(_LunarDownload):
    """NASA SVS 4930 metadata and illustration assets, not scientific flux grids.

    The two-hour rendered frames are useful qualitative references. Image
    brightness is NOT irradiance, illumination fraction or measured PV power.
    """

    SOURCE = "NASA SVS lunar illumination 4930"
    DOCUMENTATION = "https://svs.gsfc.nasa.gov/4930/"

    def metadata(
        self, *, cache_path: str | Path | None = None, refresh: bool = False
    ) -> ResearchResponse:
        """Retrieve the public metadata API linked by the SVS page."""
        return self._json(
            "https://svs.gsfc.nasa.gov/api/4930",
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, id=int, title=str, media_groups=list),
        )

    def reference_image(
        self, year: int, destination: str | Path, *, refresh: bool = False
    ) -> DownloadReceipt:
        """Download the published overview image for 2023..2030, without a timestamp claim."""
        bounded_int(year, "year", 2023, 2030)
        return self._cached_download(
            f"https://svs.gsfc.nasa.gov/vis/a000000/a004900/a004930/sp_illum_{year}_print.jpg",
            destination,
            refresh=refresh,
            max_bytes=5_000_000,
        )

    def frame(
        self, year: int, filename: str, destination: str | Path, *, refresh: bool = False
    ) -> DownloadReceipt:
        """Download an explicitly selected frame filename from the SVS frame listing.

        Frame numbering is provider-defined; read the timestamp rendered in the
        image rather than inferring it from the index.
        """
        bounded_int(year, "year", 2023, 2030)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", filename):
            raise ValueError("Use one PNG filename from the published frame listing")
        return self._cached_download(
            f"https://svs.gsfc.nasa.gov/vis/a000000/a004900/a004930/frames/1920x1080_16x9_30p/{year}/{filename}",
            destination,
            refresh=refresh,
            max_bytes=10_000_000,
        )
