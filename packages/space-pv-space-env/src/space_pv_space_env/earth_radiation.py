"""Project hemispheric Earth flux onto a panel using a Lambertian spherical Earth.

This approximation converts CERES-like outgoing TOA fluxes to panel irradiance.
It is not a bidirectional reflectance model; anisotropy and limb atmospheric
effects remain model discrepancy. Positions and surface normals must share the
Earth-fixed frame used by the latitude/longitude grid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class ProjectedEarthFlux:
    irradiance_w_m2: float
    valid_view_fraction: float
    visible_cells: int
    partial: bool
    geometric_view_factor: float
    model: str = "Lambertian spherical Earth"


def earth_grid_cell_areas(
    latitude_edges_deg: ArrayLike,
    longitude_edges_deg: ArrayLike,
    *,
    earth_radius_m: float = 6_371_008.8,
) -> np.ndarray:
    """Exact spherical grid-cell areas from increasing latitude/longitude edges."""
    lat = np.asarray(latitude_edges_deg, dtype=float)
    lon = np.asarray(longitude_edges_deg, dtype=float)
    if (
        lat.ndim != 1
        or lon.ndim != 1
        or lat.size < 2
        or lon.size < 2
        or not np.isfinite(lat).all()
        or not np.isfinite(lon).all()
        or (np.diff(lat) <= 0).any()
        or (np.diff(lon) <= 0).any()
        or lat[0] < -90
        or lat[-1] > 90
        or lon[-1] - lon[0] > 360
        or not np.isfinite(earth_radius_m)
        or earth_radius_m <= 0
    ):
        raise ValueError("Use finite increasing Earth grid edges and a positive radius")
    return (
        earth_radius_m**2
        * np.diff(np.sin(np.deg2rad(lat)))[:, None]
        * np.diff(np.deg2rad(lon))[None, :]
    )


def earth_flux_to_panel(
    spacecraft_position_m: ArrayLike,
    panel_normal: ArrayLike,
    latitude_deg: ArrayLike,
    longitude_deg: ArrayLike,
    outgoing_flux_w_m2: ArrayLike,
    cell_area_m2: ArrayLike,
    *,
    earth_radius_m: float = 6_371_008.8,
    allow_partial: bool = False,
) -> ProjectedEarthFlux:
    """Integrate visible Earth patches onto one side of a plane receiver.

    ``outgoing_flux_w_m2 / pi`` is the assumed patch radiance. Both source
    emission angle and panel incidence angle are included. Missing flux in the
    supplied visible patches produces NaN unless ``allow_partial=True``, in
    which case the returned sum covers valid cells only, without extrapolation.
    ``valid_view_fraction`` describes finite values among the supplied patches;
    it does not prove that the full visible Earth disk was supplied. Patches
    must be nonoverlapping. Center-point quadrature requires a sufficiently fine
    grid; a geometric view factor above 1.01 raises instead of being normalized.
    """
    position = np.asarray(spacecraft_position_m, dtype=float)
    normal = np.asarray(panel_normal, dtype=float)
    if (
        position.shape != (3,)
        or normal.shape != (3,)
        or not np.isfinite(position).all()
        or not np.isfinite(normal).all()
        or not np.isfinite(earth_radius_m)
        or earth_radius_m <= 0
        or np.linalg.norm(position) <= earth_radius_m
        or np.linalg.norm(normal) == 0
    ):
        raise ValueError("Use a position outside Earth and a finite nonzero panel normal")
    lat, lon, flux, area = np.broadcast_arrays(
        np.asarray(latitude_deg, dtype=float),
        np.asarray(longitude_deg, dtype=float),
        np.asarray(outgoing_flux_w_m2, dtype=float),
        np.asarray(cell_area_m2, dtype=float),
    )
    if (
        not np.isfinite(lat).all()
        or not np.isfinite(lon).all()
        or (np.abs(lat) > 90).any()
        or not np.isfinite(area).all()
        or (area <= 0).any()
        or ((flux < 0) & np.isfinite(flux)).any()
        or np.isinf(flux).any()
    ):
        raise ValueError("Invalid patch coordinates, areas, or fluxes")
    lat_r, lon_r = np.deg2rad(lat.ravel()), np.deg2rad(lon.ravel())
    outward = np.column_stack(
        (np.cos(lat_r) * np.cos(lon_r), np.cos(lat_r) * np.sin(lon_r), np.sin(lat_r))
    )
    difference = position - earth_radius_m * outward
    distance = np.linalg.norm(difference, axis=1)
    direction = difference / distance[:, None]
    emit = np.maximum(np.einsum("ij,ij->i", outward, direction), 0)
    incidence = np.maximum((-direction) @ (normal / np.linalg.norm(normal)), 0)
    weights = emit * incidence * area.ravel() / (np.pi * distance**2)
    visible = weights > 0
    valid = np.isfinite(flux.ravel())
    total_weight = float(weights.sum())
    if total_weight > 1.01:
        raise ValueError(
            "Geometric view factor exceeds one; refine the grid and check overlapping patch areas"
        )
    coverage = float(weights[valid].sum() / total_weight) if total_weight > 0 else 1.0
    partial = bool((visible & ~valid).any())
    value = float(np.sum(weights[valid] * flux.ravel()[valid]))
    if partial and not allow_partial:
        value = float("nan")
    return ProjectedEarthFlux(value, coverage, int(visible.sum()), partial, total_weight)
