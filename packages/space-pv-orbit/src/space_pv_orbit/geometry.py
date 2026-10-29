from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from space_pv_core.constants import EARTH_EQUATORIAL_RADIUS_M, SUN_RADIUS_M


@dataclass(frozen=True, slots=True)
class SolarGeometry:
    sun_vector_m: tuple[float, float, float]
    sun_distance_m: float
    sun_unit_vector: tuple[float, float, float]
    illumination_fraction: float
    cosine_aoi: float | None = None


def _vector3(value):
    arr = np.asarray(value, dtype=float)
    if arr.shape != (3,):
        raise ValueError(f"Expected a 3-vector, got shape={arr.shape}")
    return arr


def unit_vector(value) -> np.ndarray:
    arr = _vector3(value)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        raise ValueError("Cannot normalize a zero vector")
    return arr / norm


def cosine_incidence(panel_normal, sun_direction) -> float:
    value = float(np.dot(unit_vector(panel_normal), unit_vector(sun_direction)))
    return float(np.clip(value, 0.0, 1.0))


def _disc_overlap_area(radius_a: float, radius_b: float, separation: float) -> float:
    if separation >= radius_a + radius_b:
        return 0.0
    if separation <= abs(radius_a - radius_b) or separation <= 0.0:
        return math.pi * min(radius_a, radius_b) ** 2
    a = (separation**2 + radius_a**2 - radius_b**2) / (2.0 * separation * radius_a)
    b = (separation**2 + radius_b**2 - radius_a**2) / (2.0 * separation * radius_b)
    a = float(np.clip(a, -1.0, 1.0))
    b = float(np.clip(b, -1.0, 1.0))
    radicand = (
        (-separation + radius_a + radius_b)
        * (separation + radius_a - radius_b)
        * (separation - radius_a + radius_b)
        * (separation + radius_a + radius_b)
    )
    return (
        radius_a**2 * math.acos(a)
        + radius_b**2 * math.acos(b)
        - 0.5 * math.sqrt(max(radicand, 0.0))
    )


def earth_occultation_fraction(
    spacecraft_position_m,
    sun_position_m,
    *,
    earth_radius_m: float = EARTH_EQUATORIAL_RADIUS_M,
    sun_radius_m: float = SUN_RADIUS_M,
) -> float:
    r_sc = _vector3(spacecraft_position_m)
    r_sun = _vector3(sun_position_m)
    earth_from_sc = -r_sc
    sun_from_sc = r_sun - r_sc
    earth_distance = float(np.linalg.norm(earth_from_sc))
    sun_distance = float(np.linalg.norm(sun_from_sc))
    if earth_distance <= earth_radius_m:
        raise ValueError("Spacecraft position must be outside Earth")
    if sun_distance <= sun_radius_m:
        raise ValueError("Spacecraft position cannot be inside the Sun")
    earth_angular_radius = math.asin(min(1.0, earth_radius_m / earth_distance))
    sun_angular_radius = math.asin(min(1.0, sun_radius_m / sun_distance))
    separation = math.acos(
        float(np.clip(np.dot(unit_vector(earth_from_sc), unit_vector(sun_from_sc)), -1.0, 1.0))
    )
    overlap = _disc_overlap_area(sun_angular_radius, earth_angular_radius, separation)
    return float(np.clip(1.0 - overlap / (math.pi * sun_angular_radius**2), 0.0, 1.0))


def solar_geometry(spacecraft_position_m, sun_position_m, *, panel_normal=None) -> SolarGeometry:
    r_sc = _vector3(spacecraft_position_m)
    r_sun = _vector3(sun_position_m)
    sun_vector = r_sun - r_sc
    sun_distance = float(np.linalg.norm(sun_vector))
    sun_unit = unit_vector(sun_vector)
    return SolarGeometry(
        (float(sun_vector[0]), float(sun_vector[1]), float(sun_vector[2])),
        sun_distance,
        (float(sun_unit[0]), float(sun_unit[1]), float(sun_unit[2])),
        earth_occultation_fraction(r_sc, r_sun),
        cosine_incidence(panel_normal, sun_unit) if panel_normal is not None else None,
    )
