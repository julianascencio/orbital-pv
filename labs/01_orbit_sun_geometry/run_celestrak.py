"""Live example: CelesTrak OMM -> SGP4 -> Astropy Sun -> eclipse geometry.

Requires network access and ``pip install "orbital-pv[orbit]"``.
Persist the retrieved OMM with the experiment manifest for reproducibility.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import orbitalpv as opv

NORAD_ID = 25544


def main() -> None:
    omm = opv.fetch_celestrak_omm(NORAD_ID)
    satellite = opv.satellite_from_omm(omm)

    start = datetime.now(UTC).replace(second=0, microsecond=0)
    times = [start + timedelta(minutes=i * 2) for i in range(46)]
    positions_m, _ = opv.propagate_geocentric_m(satellite, times)
    sun_positions_m = opv.geocentric_sun_positions_m(times)

    visibility = [
        opv.solar_geometry(spacecraft, sun).illumination_fraction
        for spacecraft, sun in zip(positions_m, sun_positions_m, strict=True)
    ]

    print(f"satellite={omm.get('OBJECT_NAME')} norad={NORAD_ID}")
    print(
        f"samples={len(times)} min_visibility={min(visibility):.3f} "
        f"max_visibility={max(visibility):.3f}"
    )
    print(f"eclipse_samples={sum(value < 0.01 for value in visibility)}")


if __name__ == "__main__":
    main()
