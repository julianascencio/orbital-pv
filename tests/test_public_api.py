import numpy as np

import orbitalpv as opv


def test_public_version_and_core_exports() -> None:
    assert opv.__version__
    assert opv.ASTRONOMICAL_UNIT_M > 1.0e11
    assert callable(opv.am0_irradiance)
    assert callable(opv.pvwatts_dc_space)


def test_public_circular_orbit_helper() -> None:
    positions = opv.circular_orbit_positions_m(
        altitude_m=550_000.0,
        inclination_deg=51.6,
        samples=181,
    )
    assert positions.shape == (181, 3)
    radii = np.linalg.norm(positions, axis=1)
    expected = opv.EARTH_EQUATORIAL_RADIUS_M + 550_000.0
    assert np.allclose(radii, expected)


def test_public_ground_track_helper() -> None:
    positions = opv.circular_orbit_positions_m(550_000.0, 51.6, samples=25)
    elapsed = np.linspace(0.0, 5_400.0, len(positions))
    lon, lat = opv.ground_track_deg_from_eci(positions, elapsed)
    assert lon.shape == (25,)
    assert lat.shape == (25,)
    assert np.all(np.abs(lon) <= 180.0)
    assert np.all(np.abs(lat) <= 90.0)
