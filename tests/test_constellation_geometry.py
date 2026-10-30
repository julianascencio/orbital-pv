import numpy as np
import pytest

import orbitalpv as opv


def test_circular_period_matches_geostationary_rotation():
    radius = (
        opv.EARTH_STANDARD_GRAVITATIONAL_PARAMETER_M3_S2 / opv.EARTH_ROTATION_RATE_RAD_S**2
    ) ** (1.0 / 3.0)
    period = opv.circular_orbit_period_s(radius - opv.EARTH_EQUATORIAL_RADIUS_M)
    assert period == pytest.approx(2.0 * np.pi / opv.EARTH_ROTATION_RATE_RAD_S)
    assert opv.circular_orbit_period_s(650_000.0) / 60.0 == pytest.approx(97.7282, abs=0.0001)


def test_sun_synchronous_design_inclinations():
    assert opv.sun_synchronous_inclination_deg(650_000.0) == pytest.approx(97.9860, abs=0.0001)
    assert opv.sun_synchronous_inclination_deg(1_400_000.0) == pytest.approx(101.4269, abs=0.0001)
    with pytest.raises(ValueError, match="No first-order"):
        opv.sun_synchronous_inclination_deg(35_786_000.0)


def test_local_solar_time_ascending_descending_and_wrap():
    assert opv.raan_from_local_solar_time_deg(12, sun_right_ascension_deg=45) == 45
    assert opv.raan_from_local_solar_time_deg(6) == 270
    assert opv.raan_from_local_solar_time_deg(18, ascending=False) == 270
    assert opv.raan_from_local_solar_time_deg(10.5, ascending=False) == 157.5
    assert opv.raan_from_local_solar_time_deg(18, sun_right_ascension_deg=350) == 80


def test_eclipse_duration_matches_independent_shadow_geometry():
    altitude = 650_000.0
    radius = opv.EARTH_EQUATORIAL_RADIUS_M + altitude
    period = opv.circular_orbit_period_s(altitude)
    angles = np.linspace(0, 2 * np.pi, 200_000, endpoint=False)
    positions = opv.keplerian_orbit_positions_m(radius, 0.0, 0.0, true_anomaly_rad=angles)
    betas = np.array([0, 20, 58.6, 65.1, 75, 90, -20])
    for beta, predicted in zip(
        betas, opv.circular_eclipse_duration_s(altitude, betas), strict=True
    ):
        sun = np.array([np.cos(np.deg2rad(beta)), 0, np.sin(np.deg2rad(beta))])
        parallel = positions @ sun
        perpendicular = np.linalg.norm(positions - parallel[:, None] * sun, axis=1)
        inside_shadow = (parallel < 0) & (perpendicular < opv.EARTH_EQUATORIAL_RADIUS_M)
        assert predicted == pytest.approx(
            inside_shadow.mean() * period, abs=2 * period / len(angles)
        )


def test_eclipse_critical_angle_symmetry_and_finite_sun_limit():
    altitude = 1_400_000.0
    radius = opv.EARTH_EQUATORIAL_RADIUS_M + altitude
    critical = np.rad2deg(np.arcsin(opv.EARTH_EQUATORIAL_RADIUS_M / radius))
    beta = critical + 0.05
    assert opv.circular_eclipse_duration_s(altitude, beta) == 0
    assert opv.circular_eclipse_duration_s(altitude, critical) == 0
    assert opv.circular_eclipse_duration_s(altitude, -30) == opv.circular_eclipse_duration_s(
        altitude, 30
    )
    sun = opv.ASTRONOMICAL_UNIT_M * np.array(
        [np.cos(np.deg2rad(beta)), 0, np.sin(np.deg2rad(beta))]
    )
    illumination = opv.earth_occultation_fraction([-radius, 0, 0], sun)
    # Grazing finite-Sun penumbra survives beyond the point-Sun critical beta.
    assert 0 < illumination < 1


@pytest.mark.parametrize("altitude", [-1, 0, np.nan, np.inf])
def test_invalid_design_altitude(altitude):
    for function in (opv.circular_orbit_period_s, opv.sun_synchronous_inclination_deg):
        with pytest.raises(ValueError):
            function(altitude)
    with pytest.raises(ValueError):
        opv.circular_eclipse_duration_s(altitude, 0)


@pytest.mark.parametrize("beta", [91, -91, np.nan, np.inf])
def test_invalid_beta(beta):
    with pytest.raises(ValueError):
        opv.circular_eclipse_duration_s(650_000, beta)


@pytest.mark.parametrize("local_time", [-1, 24, np.nan, np.inf])
def test_invalid_local_solar_time(local_time):
    with pytest.raises(ValueError):
        opv.raan_from_local_solar_time_deg(local_time)
    with pytest.raises(ValueError):
        opv.raan_from_local_solar_time_deg(6, sun_right_ascension_deg=np.nan)
