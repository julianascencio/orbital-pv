"""Timestamped WGS84 states from real GP elements, with explicit model limits."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise

import numpy as np

from .astropy_engine import geocentric_sun_positions_m
from .geometry import earth_occultation_fraction
from .skyfield_engine import _timescale, satellite_from_omm


@dataclass(frozen=True)
class GroundTrackSample:
    timestamp: datetime
    longitude_deg: float
    latitude_deg: float
    altitude_m: float
    speed_m_s: float
    velocity_gcrs_m_s: tuple[float, float, float]
    illumination_fraction: float


def omm_epoch(omm: dict[str, object]) -> datetime:
    """Parse GP EPOCH; timezone-free OMM epochs are UTC per the GP contract."""
    if str(omm.get("TIME_SYSTEM", "UTC")).upper() != "UTC":
        raise ValueError("Only UTC GP elements are supported")
    epoch = datetime.fromisoformat(str(omm["EPOCH"]).replace("Z", "+00:00"))
    return epoch.replace(tzinfo=UTC) if epoch.tzinfo is None else epoch.astimezone(UTC)


def propagate_ground_track(
    omm: dict[str, object],
    times: Sequence[datetime],
    *,
    max_element_age_days: float = 14,
    sun_positions_m: np.ndarray | None = None,
) -> list[GroundTrackSample]:
    """Propagate OMM with SGP4 and transform to WGS84 geodetic coordinates.

    Velocity and its magnitude are geocentric GCRS inertial quantities, not
    ground speed. Altitude is height above the WGS84 ellipsoid. Illumination
    reuses the finite-Sun/spherical-Earth occultation model and Astropy GCRS Sun
    vectors; it is an estimate, not measured PV output. Optional Sun vectors
    must be GCRS metres at the exact supplied timestamps.

    Reject naive/unsorted timestamps, SGP4 errors and element sets farther than
    ``max_element_age_days`` from any requested time (including future epochs).
    This cutoff is a display policy, not an orbital accuracy guarantee.
    """
    from skyfield.api import wgs84

    if not times or len(times) > 10000:
        raise ValueError("Supply between 1 and 10000 timestamps")
    if any(t.tzinfo is None or t.utcoffset() is None for t in times):
        raise ValueError("Tracking timestamps must be timezone-aware")
    timestamps = [t.astimezone(UTC) for t in times]
    if any(a >= b for a, b in pairwise(timestamps)):
        raise ValueError("Tracking timestamps must increase strictly")
    if not np.isfinite(max_element_age_days) or not 0 < max_element_age_days <= 14:
        raise ValueError("max_element_age_days must be in (0, 14]")
    if str(omm.get("CENTER_NAME", "EARTH")).upper() != "EARTH":
        raise ValueError("Only Earth-centred GP elements are supported")
    if str(omm.get("REF_FRAME", "TEME")).upper() != "TEME":
        raise ValueError("SGP4 GP elements must use TEME")
    if str(omm.get("MEAN_ELEMENT_THEORY", "SGP4")).upper() != "SGP4":
        raise ValueError("GP elements must use SGP4")
    epoch = omm_epoch(omm)
    if max(abs((t - epoch).total_seconds()) for t in timestamps) > max_element_age_days * 86400:
        raise ValueError("Element epoch is outside the allowed propagation age")
    satellite = satellite_from_omm(omm)
    state = satellite.at(_timescale().from_datetimes(timestamps))
    if np.any(np.asarray(state.message, dtype=object) != None):  # noqa: E711
        raise ValueError("SGP4 reported an invalid or decayed orbit")
    xyz = np.asarray(state.position.m).T
    velocity = np.asarray(state.velocity.m_per_s).T
    if not np.all(np.isfinite(xyz)) or not np.all(np.isfinite(velocity)):
        raise ValueError("SGP4 produced non-finite states")
    geodetic = wgs84.geographic_position_of(state)
    sun = (
        geocentric_sun_positions_m(timestamps)
        if sun_positions_m is None
        else np.asarray(sun_positions_m)
    )
    if sun.shape != xyz.shape or not np.all(np.isfinite(sun)):
        raise ValueError("sun_positions_m must be finite GCRS vectors of shape (n, 3)")
    return [
        GroundTrackSample(
            timestamp=t,
            longitude_deg=float(geodetic.longitude.degrees[i]),
            latitude_deg=float(geodetic.latitude.degrees[i]),
            altitude_m=float(geodetic.elevation.m[i]),
            speed_m_s=float(np.linalg.norm(velocity[i])),
            velocity_gcrs_m_s=(float(velocity[i, 0]), float(velocity[i, 1]), float(velocity[i, 2])),
            illumination_fraction=earth_occultation_fraction(xyz[i], sun[i]),
        )
        for i, t in enumerate(timestamps)
    ]
