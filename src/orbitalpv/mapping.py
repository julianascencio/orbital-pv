"""Plot native satellite inputs and original mapped solar features.

The utilities add presentation to :func:`orbitalpv.load_pv_site`: they do not
segment panels, assemble OSM multipolygons, resample images or infer capacity.
Matplotlib and Rasterio are imported only when a plot is requested.
"""

from __future__ import annotations

import importlib
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np

import space_pv_connectors.ground_site
from space_pv_connectors.ground_raster import GroundImage
from space_pv_connectors.ground_site import PVSite

from .pv_detection import PVFootprintPrediction

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

_SCL_NAMES = (
    "No data",
    "Saturated/defective",
    "Topographic shadow",
    "Cloud shadow",
    "Vegetation",
    "Not vegetated",
    "Water",
    "Unclassified",
    "Cloud: medium",
    "Cloud: high",
    "Cirrus",
    "Snow/ice",
)
_SCL_COLORS = (
    "#000000",
    "#ff0000",
    "#555555",
    "#805000",
    "#008000",
    "#ffe65a",
    "#0000ff",
    "#808080",
    "#c0c0c0",
    "#ffffff",
    "#64c8ff",
    "#ff96ff",
)


def _optional(module: str) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ImportError(
            f"PV mapping plots require {module.split('.')[0]}; install "
            "python -m pip install 'orbital-pv[ground,examples]'."
        ) from exc


def _image(site: PVSite, asset: str, bands: int) -> GroundImage:
    if asset not in site.images:
        raise ValueError(f"This plot requires the {asset!r} asset in site.images")
    image = site.images[asset]
    if image.asset_key != asset or image.scene_id != site.item.get("id"):
        raise ValueError(f"The {asset!r} image must match the site's selected scene and asset")
    if image.data.ndim != 3 or image.data.shape[0] != bands:
        raise ValueError(
            f"The {asset!r} image must have {bands} bands in (band, row, column) order"
        )
    return image


def _acquired(site: PVSite) -> datetime:
    value = site.item.get("properties", {}).get("datetime")
    try:
        acquired = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if acquired.tzinfo is None:
            raise ValueError
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(
            "The selected scene needs a valid timezone-aware acquisition datetime"
        ) from exc
    return acquired.astimezone(UTC)


def _grid(image: GroundImage) -> tuple[tuple, str, str, str]:
    a, b, _c, d, e, _f = image.transform
    if b != 0 or d != 0 or a <= 0 or e >= 0:
        raise ValueError("Mapping plots require a north-up native image grid")
    crs = _optional("rasterio.crs").CRS.from_user_input(image.crs)
    if crs.is_geographic:
        unit, x_name, y_name = "°", "Longitude", "Latitude"
    else:
        unit = "m" if crs.linear_units_factor[1] == 1 else crs.linear_units
        x_name, y_name = "Easting", "Northing"
    resolution = f"{a:g}" if math.isclose(a, abs(e)) else f"{a:g} by {abs(e):g}"
    left, bottom, right, top = image.bounds
    return (
        (left, right, bottom, top),
        f"{x_name} [{unit}], {image.crs}",
        f"{y_name} [{unit}]",
        f"{resolution} {unit}",
    )


def _axes_labels(ax: Axes, grid: tuple) -> None:
    ticker = _optional("matplotlib.ticker")
    ax.set(xlabel=grid[1], ylabel=grid[2])
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=4))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=4))


def _point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        lon, lat = float(value["lon"]), float(value["lat"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90:
        return lon, lat
    return None


def _draw_osm(ax: Axes, site: PVSite, crs: str) -> None:
    transform = _optional("rasterio.warp").transform
    labels: set[str] = set()
    elements = site.osm.get("elements", [])
    for element in elements:
        plant = element.get("tags", {}).get("power") == "plant"
        color, width = ("#ffd700", 1.8) if plant else ("#00ffff", 0.8)
        kind = "plant" if plant else "solar-feature"
        objects = [element, *element.get("members", [])]
        for obj in objects:
            point = _point(obj) if obj.get("type") == "node" else None
            if point is not None:
                x, y = transform("EPSG:4326", crs, [point[0]], [point[1]])
                label = f"OSM {kind} locations"
                ax.scatter(x, y, s=12, color=color, label=label if label not in labels else None)
                labels.add(label)
            geometry = obj.get("geometry")
            if not isinstance(geometry, list):
                continue
            run: list[tuple[float, float]] = []
            for value in [*geometry, None]:
                point = _point(value)
                if point is not None:
                    run.append(point)
                else:
                    if len(run) >= 2:
                        x, y = transform("EPSG:4326", crs, [p[0] for p in run], [p[1] for p in run])
                        label = f"OSM {kind} outlines"
                        ax.plot(
                            x,
                            y,
                            color=color,
                            linewidth=width,
                            label=label if label not in labels else None,
                        )
                        labels.add(label)
                    run = []
    if labels:
        ax.legend(fontsize=8, loc="upper right")
    else:
        message = "No drawable OSM geometry" if elements else "No mapped solar features returned"
        ax.text(
            0.02,
            0.98,
            message,
            transform=ax.transAxes,
            va="top",
            fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
        )


def plot_pv_site(
    site: space_pv_connectors.ground_site.PVSite,
    *,
    overlay_osm: bool = False,
    ax: Axes | None = None,
) -> Axes:
    """Show native RGB, optionally with original OSM outlines and locations.

    Parameters
    ----------
    site : space_pv_connectors.ground_site.PVSite
        Inputs returned by :func:`orbitalpv.load_pv_site`, including ``visual``.
    overlay_osm : bool, default False
        Transform the raw WGS84 map coordinates into the image CRS. Separate
        ways, relation members and incomplete geometry runs remain separate.
        Outlines are source map features, not image-derived panel labels.
    ax : matplotlib.axes.Axes, optional
        Draw into existing axes and place attribution beneath those axes;
        otherwise create an attributed figure. Use constrained/tight layout
        when composing multiple supplied axes. Existing figure credits remain
        unchanged.

    Returns
    -------
    matplotlib.axes.Axes
        Axes available for further annotations. Call ``plt.show()`` yourself.

    Notes
    -----
    RGB nodata samples are filled with zero only for display. Source arrays,
    masks and geometry are unchanged. Image and OSM dates are shown separately.
    """
    image = _image(site, "visual", 3)
    acquired, grid = _acquired(site), _grid(image)
    plt = _optional("matplotlib.pyplot")
    owns_figure = ax is None
    if owns_figure:
        _, ax = plt.subplots(figsize=(8, 7), layout="constrained")
    ax.imshow(np.moveaxis(image.data.filled(0), 0, -1), extent=grid[0], interpolation="none")
    footer = f"Modified Copernicus Sentinel data ({acquired.year}) / Element 84"
    if overlay_osm:
        _draw_osm(ax, site, image.crs)
        timestamp = site.osm.get("osm3s", {}).get("timestamp_osm_base", "unknown")
        osm_date = str(timestamp).partition("T")[0]
        title = f"{site.name}\nImage {acquired.date()} · OSM {osm_date}"
        footer += "\n© OpenStreetMap contributors (ODbL) · independent image and map dates"
    else:
        title = f"{site.name}\nSentinel-2 RGB · {acquired:%d %B %Y}"
        footer += f" · native {grid[3]} pixels"
    ax.set(title=title, xlim=grid[0][:2], ylim=grid[0][2:])
    _axes_labels(ax, grid)
    if owns_figure:
        ax.figure.supxlabel(footer, fontsize=8)
    else:
        ax.text(
            0.5,
            -0.24,
            footer.replace(" / Element 84", "\nElement 84"),
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=7,
        )
    return ax


def plot_pv_site_quality(
    site: space_pv_connectors.ground_site.PVSite,
) -> tuple[Figure, np.ndarray]:
    """Show calibrated red reflectance and the native SCL quality categories.

    ``red`` and ``scl`` assets are required. Red calibration uses the source's
    explicit scale/offset, preserving nodata and negative reflectance. The
    display range is 0 to 0.5; colorbar extensions flag values outside that range.
    SCL remains on its native grid with its original integer categories 0 to 11.
    No resampling, cloud masking or photovoltaic classification is performed.

    Returns the figure and two image axes; ``plt.show()`` remains with the
    caller. Both images retain their own native extents and coordinate labels.
    """
    red, scl = _image(site, "red", 1), _image(site, "scl", 1)
    reflectance = red.reflectance()[0]
    present = np.unique(scl.data.compressed())
    if not np.issubdtype(scl.data.dtype, np.integer) or np.any((present < 0) | (present > 11)):
        raise ValueError("SCL must contain integer category codes from 0 through 11")
    acquired = _acquired(site)
    red_grid, scl_grid = _grid(red), _grid(scl)
    plt, colors = _optional("matplotlib.pyplot"), _optional("matplotlib.colors")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    im = axes[0].imshow(
        reflectance, extent=red_grid[0], cmap="magma", vmin=0, vmax=0.5, interpolation="none"
    )
    values = reflectance.compressed()
    below, above = bool(np.any(values < 0)), bool(np.any(values > 0.5))
    extend = "both" if below and above else "min" if below else "max" if above else "neither"
    fig.colorbar(
        im, ax=axes[0], shrink=0.7, label="B04 surface reflectance [dimensionless]", extend=extend
    )
    axes[0].set_title(f"Explicit red-band calibration · {red_grid[3]}")
    im = axes[1].imshow(
        scl.data[0],
        extent=scl_grid[0],
        cmap=colors.ListedColormap(_SCL_COLORS),
        norm=colors.BoundaryNorm(np.arange(-0.5, 12.5), 12),
        interpolation="none",
    )
    bar = fig.colorbar(im, ax=axes[1], shrink=0.7, ticks=present)
    bar.ax.set_yticklabels([_SCL_NAMES[int(code)] for code in present])
    axes[1].set_title(f"Source scene classification · {scl_grid[3]}")
    for ax, grid in zip(axes, (red_grid, scl_grid), strict=True):
        _axes_labels(ax, grid)
    fig.suptitle(f"{site.name} · {acquired:%d %B %Y}")
    fig.supxlabel(
        f"Modified Copernicus Sentinel data ({acquired.year}) / Element 84 · no resampling",
        fontsize=8,
    )
    return fig, axes


def plot_pv_detection(
    site: space_pv_connectors.ground_site.PVSite,
    prediction: PVFootprintPrediction,
    *,
    reference_labels: np.ndarray | None = None,
    reference_label: str = "Separate reference labels",
    reference_credit: str | None = None,
) -> tuple[Figure, np.ndarray]:
    """Compare a real RGB image, model scores and image-derived PV footprints.

    Inference output must match the site's red-band native grid and scene.
    Optional -1/0/1 reference labels add separate orange outlines; they are
    not used to create or clip the prediction. Unknown references remain
    unknown. Supply a source-specific ``reference_label`` and attribution in
    ``reference_credit`` when displaying mapped reference data. The function
    returns the figure and three axes for customization.
    """
    rgb, red = _image(site, "visual", 3), _image(site, "red", 1)
    metadata = prediction.metadata
    if (
        metadata.get("scene_id") != red.scene_id
        or metadata.get("crs") != red.crs
        or tuple(metadata.get("transform", ())) != red.transform
        or tuple(metadata.get("bounds", ())) != red.bounds
        or prediction.mask.shape != red.data.shape[1:]
        or prediction.probabilities.shape != prediction.mask.shape
        or rgb.transform != red.transform
        or rgb.crs != red.crs
        or rgb.data.shape[1:] != red.data.shape[1:]
    ):
        raise ValueError("Prediction and RGB must match the site's red-band scene and native grid")
    if reference_labels is not None:
        reference = np.ma.asarray(reference_labels)
        if (
            reference.shape != prediction.mask.shape
            or not np.isin(reference.compressed(), (-1, 0, 1)).all()
        ):
            raise ValueError("Reference labels must match the prediction grid and contain -1/0/1")
        reference_labels = np.ma.filled(reference.astype(np.int8), -1)
    plt = _optional("matplotlib.pyplot")
    colors = _optional("matplotlib.colors")
    lines = _optional("matplotlib.lines")
    grid, acquired = _grid(red), _acquired(site)
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.4), layout="constrained")
    visual = np.moveaxis(rgb.data.filled(0), 0, -1)
    axes[0].imshow(visual, extent=grid[0], interpolation="nearest")
    axes[0].set_title("Sentinel-2 RGB\n" + grid[3])
    scores = axes[1].imshow(
        prediction.probabilities,
        extent=grid[0],
        cmap="magma",
        vmin=0,
        vmax=1,
        interpolation="nearest",
    )
    axes[1].set_facecolor("#d9d9d9")
    axes[1].set_title("PV class score\nUncalibrated model probability")
    fig.colorbar(scores, ax=axes[1], shrink=0.74, label="Score")
    axes[2].imshow(visual, extent=grid[0], interpolation="nearest")
    mask = np.ma.masked_where(~prediction.mask.filled(False), prediction.mask.filled(False))
    axes[2].imshow(
        mask,
        extent=grid[0],
        cmap=colors.ListedColormap(["#00e5ff"]),
        alpha=0.65,
        interpolation="nearest",
    )
    handles = [lines.Line2D([], [], color="#00b8cc", linewidth=5, label="Image prediction")]
    if reference_labels is not None and np.any(reference_labels == 1):
        a, _, c, _, e, f = red.transform
        x = c + a * (np.arange(prediction.mask.shape[1]) + 0.5)
        y = f + e * (np.arange(prediction.mask.shape[0]) + 0.5)
        axes[2].contour(
            x,
            y,
            (reference_labels == 1).astype(float),
            levels=[0.5],
            colors=["#ffb000"],
            linewidths=0.9,
        )
        handles.append(lines.Line2D([], [], color="#ffb000", label=reference_label))
    axes[2].legend(handles=handles, fontsize=8, loc="upper right")
    axes[2].set_title(
        f"Predicted footprint: {prediction.area_m2 / 10000:.2f} ha\n"
        f"Score ≥ {metadata['threshold']:g}; region ≥ {metadata['min_area_m2']:g} m²"
    )
    for ax in axes:
        _axes_labels(ax, grid)
        ax.set(xlim=grid[0][:2], ylim=grid[0][2:])
    training_note = "training area" if metadata.get("overlaps_training_area") else "unseen area"
    fig.suptitle(f"{site.name} · {acquired:%d %B %Y}\nImage-only inference · {training_note}")
    footer = (
        f"Modified Copernicus Sentinel data ({acquired.year}) / Element 84 · "
        "Pixel footprints are not individual modules"
    )
    if reference_labels is not None:
        footer += "\n" + (
            reference_credit
            or "Reference labels are supplied separately; verify their source and date"
        )
    fig.supxlabel(footer, fontsize=8)
    return fig, axes


__all__ = ["plot_pv_detection", "plot_pv_site", "plot_pv_site_quality"]
