"""Lunar south-pole terrain, finite Sun visibility and thermal boundary inputs.

Coordinates are planetocentric, east-positive, MOON_ME_DE421. Terrain heights
are metres above the 1737400 m sphere. A sampled DEM is not a complete horizon:
unresolved peaks and terrain outside its extent remain modelling limitations.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from space_pv_core.constants import ASTRONOMICAL_UNIT_M, SUN_RADIUS_M
from space_pv_orbit.geometry import earth_occultation_fraction
from space_pv_orbit.spice_engine import positions_m, utc_to_ephemeris_seconds

MOON_RADIUS_M = 1_737_400.0
LUNAR_FRAME = "MOON_ME_DE421"


def _finite(value: ArrayLike, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite")
    return result


def south_polar_lonlat(x_m: ArrayLike, y_m: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    """Invert spherical stereographic coordinates (lat_0=-90, lon_0=0, k=1).

    Return longitude [0, 360) and latitude in degrees. At the projection pole,
    longitude is set to zero. +Y points towards longitude zero, +X to 90 east.
    """
    x, y = np.broadcast_arrays(_finite(x_m, "x_m"), _finite(y_m, "y_m"))
    longitude = np.mod(np.rad2deg(np.arctan2(x, y)), 360)
    latitude = -90 + np.rad2deg(2 * np.arctan(np.hypot(x, y) / (2 * MOON_RADIUS_M)))
    return longitude, latitude


def lunar_surface_position(
    longitude_deg: ArrayLike, latitude_deg: ArrayLike, elevation_m: ArrayLike = 0.0
) -> np.ndarray:
    """Cartesian body-fixed positions, last dimension XYZ, in metres."""
    lon, lat, z = np.broadcast_arrays(
        _finite(longitude_deg, "longitude_deg"),
        _finite(latitude_deg, "latitude_deg"),
        _finite(elevation_m, "elevation_m"),
    )
    if np.any(np.abs(lat) > 90) or np.any(z <= -MOON_RADIUS_M):
        raise ValueError("Invalid lunar latitude or radius")
    lon, lat = np.deg2rad(lon), np.deg2rad(lat)
    return (MOON_RADIUS_M + z)[..., None] * np.stack(
        [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1
    )


def _enu(longitude_deg: float, latitude_deg: float) -> np.ndarray:
    lon, lat = np.deg2rad([longitude_deg, latitude_deg])
    return np.array(
        [
            [-np.sin(lon), np.cos(lon), 0],
            [-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)],
            [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)],
        ]
    )


@dataclass(frozen=True)
class LunarTerrain:
    """Regular south-polar stereographic grid, axes increasing, elevation[y,x].

    Missing elevations are allowed as NaN and are never replaced by zero. The
    horizon routine rejects missing cells. Use a valid bounded window explicitly
    rather than silently bridging data gaps. Units and projection are fixed.
    """

    x_m: np.ndarray
    y_m: np.ndarray
    elevation_m: np.ndarray

    def __post_init__(self) -> None:
        for name in ("x_m", "y_m"):
            a = _finite(getattr(self, name), name)
            if a.ndim != 1 or len(a) < 2 or np.any(np.diff(a) <= 0):
                raise ValueError(f"{name} must be a strictly increasing axis")
            if not np.allclose(np.diff(a), np.diff(a)[0]):
                raise ValueError("Terrain axes must be regularly spaced")
            object.__setattr__(self, name, a.copy())
        z = np.asarray(self.elevation_m, dtype=float)
        if z.shape != (len(self.y_m), len(self.x_m)):
            raise ValueError("elevation_m shape must be (len(y_m), len(x_m))")
        if np.isinf(z).any() or np.any(z <= -MOON_RADIUS_M):
            raise ValueError("Invalid terrain elevations")
        object.__setattr__(self, "elevation_m", z.copy())

    def height(self, x_m: float, y_m: float) -> float:
        """Bilinear elevation; reject out-of-bounds points or missing neighbours."""
        if not np.isfinite([x_m, y_m]).all():
            raise ValueError("Site coordinates must be finite")
        if not self.x_m[0] <= x_m <= self.x_m[-1] or not self.y_m[0] <= y_m <= self.y_m[-1]:
            raise ValueError("Site is outside the terrain grid")
        j = int(np.clip(np.searchsorted(self.x_m, x_m) - 1, 0, len(self.x_m) - 2))
        i = int(np.clip(np.searchsorted(self.y_m, y_m) - 1, 0, len(self.y_m) - 2))
        a = (x_m - self.x_m[j]) / (self.x_m[j + 1] - self.x_m[j])
        b = (y_m - self.y_m[i]) / (self.y_m[i + 1] - self.y_m[i])
        block = self.elevation_m[i : i + 2, j : j + 2]
        if not np.isfinite(block).all():
            raise ValueError("Site intersects missing terrain")
        return float(np.array([1 - b, b]) @ block @ np.array([1 - a, a]))


def terrain_horizon(
    terrain: LunarTerrain,
    *,
    site_x_m: float,
    site_y_m: float,
    tower_height_m: float,
    azimuth_bins: int = 360,
    site_elevation_m: float | None = None,
    minimum_distance_m: float = 0.0,
) -> pd.DataFrame:
    """Maximum sampled terrain elevation angle per azimuth sector, with curvature.

    Ray directions are evaluated in the site's true east/north/up basis, not
    projection-grid north. Every DEM pixel centre contributes to one sector.
    This sector-envelope approximation can over-shade within a sector while
    missing subpixel obstacles; refine DEM and sectors before engineering use.
    ``site_elevation_m`` holds the observer at one common ground elevation when
    combining grids. ``minimum_distance_m`` excludes inner samples from coarser
    layers; the caller must cover the excluded region with a finer grid.
    The reported angular coverage is finite and not an assertion that distant
    terrain has been checked. Heights are measured above interpolated ground.
    """
    if not np.isfinite(tower_height_m) or tower_height_m < 0:
        raise ValueError("tower_height_m must be finite and non-negative")
    if not np.isfinite(minimum_distance_m) or minimum_distance_m < 0:
        raise ValueError("minimum_distance_m must be finite and non-negative")
    if isinstance(azimuth_bins, bool) or not isinstance(azimuth_bins, int) or azimuth_bins < 4:
        raise ValueError("azimuth_bins must be an integer >= 4")
    if not np.isfinite(terrain.elevation_m).all():
        raise ValueError("Horizon requires a terrain window without missing elevations")
    ground = terrain.height(site_x_m, site_y_m)
    if site_elevation_m is not None:
        if not np.isfinite(site_elevation_m) or site_elevation_m <= -MOON_RADIUS_M:
            raise ValueError("site_elevation_m must be a finite valid lunar elevation")
        ground = float(site_elevation_m)
    lon, lat = south_polar_lonlat(site_x_m, site_y_m)
    observer = lunar_surface_position(lon, lat, ground + tower_height_m)
    x, y = np.meshgrid(terrain.x_m, terrain.y_m)
    lons, lats = south_polar_lonlat(x, y)
    points = lunar_surface_position(lons, lats, terrain.elevation_m)
    vectors = (points - observer).reshape(-1, 3) @ _enu(float(lon), float(lat)).T
    distance = np.hypot(vectors[:, 0], vectors[:, 1])
    valid = distance > max(1e-6, minimum_distance_m)
    azimuth = np.mod(np.rad2deg(np.arctan2(vectors[:, 0], vectors[:, 1])), 360)
    sectors = np.minimum((azimuth / 360 * azimuth_bins).astype(int), azimuth_bins - 1)
    angles = np.rad2deg(np.arctan2(vectors[:, 2], distance))
    horizon = np.full(azimuth_bins, -np.inf)
    farthest = np.zeros(azimuth_bins)
    counts = np.zeros(azimuth_bins, dtype=int)
    np.maximum.at(horizon, sectors[valid], angles[valid])
    np.maximum.at(farthest, sectors[valid], distance[valid])
    np.add.at(counts, sectors[valid], 1)
    if np.any(counts == 0):
        raise ValueError("Empty horizon sectors: expand terrain or reduce azimuth_bins")
    result = pd.DataFrame(
        {
            "azimuth_deg": (np.arange(azimuth_bins) + 0.5) * 360 / azimuth_bins,
            "horizon_elevation_deg": horizon,
            "maximum_sample_distance_m": farthest,
            "terrain_samples": counts,
        }
    )
    result.attrs.update(
        frame=LUNAR_FRAME,
        ground_elevation_m=ground,
        tower_height_m=tower_height_m,
        minimum_directional_extent_m=float(farthest.min()),
        model="pixel-centre sector envelope; finite DEM extent and resolution",
    )
    return result


def solar_disc_visibility(
    elevation_deg: ArrayLike, horizon_deg: ArrayLike, angular_radius_deg: ArrayLike = 0.2666
) -> np.ndarray:
    """Visible area of a uniform solar disc above a locally straight horizon.

    Neglect limb darkening and horizon variation across the disc. No atmospheric
    refraction is applied. This is a geometric area fraction, not a measurement.
    """
    e, h, r = np.broadcast_arrays(
        _finite(elevation_deg, "elevation_deg"),
        _finite(horizon_deg, "horizon_deg"),
        _finite(angular_radius_deg, "angular_radius_deg"),
    )
    if np.any(np.abs(e) > 90) or np.any(np.abs(h) > 90) or np.any((r <= 0) | (r >= 90)):
        raise ValueError("Invalid solar/horizon angles")
    z = np.clip((e - h) / r, -1, 1)
    return (np.arccos(-z) + z * np.sqrt(np.maximum(1 - z**2, 0))) / np.pi


def lunar_ephemeris(utc_timestamps: list[str]) -> pd.DataFrame:
    """Sun/Earth vectors using explicitly preloaded DE421 SPICE kernels.

    Reuses OrbitalPV's SPICE engine and does not change the global kernel pool.
    UTC input must include ``Z``. Output elapsed seconds are ET (SI seconds).
    Vectors are simultaneous geometric positions, not light-time corrected;
    the approximation is recorded for reproducible terrain screening studies.
    """
    times = utc_to_ephemeris_seconds(utc_timestamps)
    if len(times) < 2 or np.any(np.diff(times) <= 0):
        raise ValueError("At least two increasing UTC timestamps are required")
    sun = positions_m("SUN", times.tolist(), frame=LUNAR_FRAME, observer="MOON")
    earth = positions_m("EARTH", times.tolist(), frame=LUNAR_FRAME, observer="MOON")
    result = pd.DataFrame({"utc": utc_timestamps, "time_s": times - times[0]})
    for name, positions in (("sun", sun), ("earth", earth)):
        for i, axis in enumerate("xyz"):
            result[f"{name}_{axis}_m"] = positions[:, i]
    result.attrs.update(frame=LUNAR_FRAME, aberration="NONE", time_basis="UTC inputs; ET elapsed")
    return result


def lunar_solar_geometry(
    sun_position_m: ArrayLike,
    earth_position_m: ArrayLike,
    *,
    longitude_deg: float,
    latitude_deg: float,
    elevation_m: float,
) -> pd.DataFrame:
    """Topocentric Sun angles and direct-normal flux, including Earth eclipses.

    Input vectors originate at the Moon centre in MOON_ME_DE421. Spherical,
    opaque Earth occultation reuses the orbit model; terrestrial atmospheric
    transmission during lunar eclipses is omitted. Terrain shading is separate.
    """
    sun, earth = (
        _finite(sun_position_m, "sun_position_m"),
        _finite(earth_position_m, "earth_position_m"),
    )
    if sun.ndim != 2 or sun.shape[1] != 3 or earth.shape != sun.shape or len(sun) == 0:
        raise ValueError("Sun/Earth positions must have matching nonempty (N,3) shapes")
    site = lunar_surface_position(longitude_deg, latitude_deg, elevation_m)
    if site.shape != (3,):
        raise ValueError("Site coordinates must be scalar")
    vectors = (sun - site) @ _enu(longitude_deg, latitude_deg).T
    distance = np.linalg.norm(vectors, axis=1)
    if np.any(distance <= SUN_RADIUS_M):
        raise ValueError("Observer must be outside the Sun")
    earth_visible = np.array(
        [earth_occultation_fraction(site - e, s - e) for s, e in zip(sun, earth, strict=True)]
    )
    result = pd.DataFrame(
        {
            "azimuth_deg": np.mod(np.rad2deg(np.arctan2(vectors[:, 0], vectors[:, 1])), 360),
            "elevation_deg": np.rad2deg(
                np.arctan2(vectors[:, 2], np.hypot(vectors[:, 0], vectors[:, 1]))
            ),
            "sun_distance_au": distance / ASTRONOMICAL_UNIT_M,
            "solar_angular_radius_deg": np.rad2deg(np.arcsin(SUN_RADIUS_M / distance)),
            "earth_visible_fraction": earth_visible,
            "unobstructed_dni_w_m2": 1361 * (ASTRONOMICAL_UNIT_M / distance) ** 2,
        }
    )
    result.attrs["frame"] = LUNAR_FRAME
    return result
