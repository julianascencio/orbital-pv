import math

import numpy as np

from space_pv_core.constants import ASTRONOMICAL_UNIT_M, EARTH_EQUATORIAL_RADIUS_M
from space_pv_orbit.geometry import cosine_incidence, earth_occultation_fraction, solar_geometry


def test_cosine_incidence():
    assert cosine_incidence([1, 0, 0], [1, 0, 0]) == 1.0
    assert cosine_incidence([1, 0, 0], [-1, 0, 0]) == 0.0
    assert math.isclose(cosine_incidence([1, 0, 0], [1, 1, 0]), math.sqrt(0.5))


def test_eclipse_and_sunlight_geometry():
    altitude = 400_000.0
    r = EARTH_EQUATORIAL_RADIUS_M + altitude
    sun = np.array([ASTRONOMICAL_UNIT_M, 0.0, 0.0])
    assert earth_occultation_fraction([-r, 0.0, 0.0], sun) < 1e-9
    assert earth_occultation_fraction([r, 0.0, 0.0], sun) > 0.999999


def test_solar_geometry_aoi():
    r = EARTH_EQUATORIAL_RADIUS_M + 400_000.0
    geometry = solar_geometry([r, 0, 0], [ASTRONOMICAL_UNIT_M, 0, 0], panel_normal=[1, 0, 0])
    assert geometry.cosine_aoi is not None
    assert geometry.cosine_aoi > 0.999999
    assert geometry.illumination_fraction > 0.999999
