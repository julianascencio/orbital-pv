"""Live example: CelesTrak OMM -> Skyfield SGP4 -> Astropy Sun -> eclipse geometry.

Requires network access and the orbit dependency group. The retrieved OMM should be saved
with the final experiment manifest for reproducibility in serious runs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from space_pv_connectors import CelesTrakConnector
from space_pv_orbit.astropy_engine import geocentric_sun_positions_m
from space_pv_orbit.geometry import solar_geometry
from space_pv_orbit.skyfield_engine import propagate_geocentric_m, satellite_from_omm

NORAD_ID = 25544


def main() -> None:
    with CelesTrakConnector() as connector:
        omm = connector.fetch_gp(catnr=NORAD_ID)[0]

    satellite = satellite_from_omm(omm)
    start = datetime.now(UTC).replace(second=0, microsecond=0)
    times = [start + timedelta(minutes=i * 2) for i in range(46)]
    positions_m, _ = propagate_geocentric_m(satellite, times)
    sun_positions_m = geocentric_sun_positions_m(times)

    visibility = [
        solar_geometry(sc, sun).illumination_fraction
        for sc, sun in zip(positions_m, sun_positions_m, strict=True)
    ]
    print(f"satellite={omm.get('OBJECT_NAME')} norad={NORAD_ID}")
    print(
        f"samples={len(times)} min_visibility={min(visibility):.3f} max_visibility={max(visibility):.3f}"
    )
    print(f"eclipse_samples={sum(v < 0.01 for v in visibility)}")


if __name__ == "__main__":
    main()
