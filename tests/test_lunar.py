from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from orbitalpv import PvwattsReference, lunar, physics


def terrain():
    axes = np.arange(-2000, 2001, 50)
    x, y = np.meshgrid(axes, axes)
    return lunar.LunarTerrain(axes, axes, 200 * np.exp(-((x - 700) ** 2 + y**2) / 200**2))


def horizon(angle=0):
    return pd.DataFrame(
        {"azimuth_deg": np.arange(0.5, 360), "horizon_elevation_deg": np.full(360, angle)}
    )


def geometry(elevation=30, azimuth=0):
    return pd.DataFrame(
        {
            "azimuth_deg": [azimuth],
            "elevation_deg": [elevation],
            "solar_angular_radius_deg": [0.27],
            "earth_visible_fraction": [1.0],
            "unobstructed_dni_w_m2": [1361.0],
        }
    )


def test_polar_projection_and_cartesian_axes():
    lon, lat = lunar.south_polar_lonlat([0, 1000, 0], [0, 0, 1000])
    np.testing.assert_allclose(lon, [0, 90, 0])
    assert lat[0] == -90
    np.testing.assert_allclose(lunar.lunar_surface_position(0, 0), [lunar.MOON_RADIUS_M, 0, 0])
    np.testing.assert_allclose(
        lunar.lunar_surface_position(0, -90), [0, 0, -lunar.MOON_RADIUS_M], atol=1e-9
    )


def test_interpolated_height_bounds_and_missing():
    t = lunar.LunarTerrain(np.array([0, 10]), np.array([0, 10]), np.array([[0, 10], [20, 30]]))
    assert t.height(5, 5) == 15
    assert t.height(10, 10) == 30
    with pytest.raises(ValueError, match="outside"):
        t.height(-1, 5)
    with pytest.raises(ValueError, match="regularly"):
        lunar.LunarTerrain(np.array([0, 1, 3]), np.array([0, 1]), np.zeros((2, 3)))
    t.elevation_m[0, 0] = np.nan
    with pytest.raises(ValueError, match="missing"):
        t.height(5, 5)


def test_horizon_height_monotonic_and_true_north():
    t = terrain()
    low = lunar.terrain_horizon(t, site_x_m=0, site_y_m=0, tower_height_m=2, azimuth_bins=180)
    high = lunar.terrain_horizon(t, site_x_m=0, site_y_m=0, tower_height_m=20, azimuth_bins=180)
    assert np.all(high.horizon_elevation_deg <= low.horizon_elevation_deg + 1e-9)
    peak = low.iloc[low.horizon_elevation_deg.argmax()]
    assert abs(peak.azimuth_deg - 90) < 5  # mountain at projected +X, east at lon=0
    assert peak.horizon_elevation_deg > 10
    assert low.attrs["minimum_directional_extent_m"] > 1500


def test_spherical_curvature_not_flat_terrain():
    axes = np.arange(-10_000, 10_001, 100)
    t = lunar.LunarTerrain(axes, axes, np.zeros((len(axes), len(axes))))
    h = lunar.terrain_horizon(t, site_x_m=0, site_y_m=0, tower_height_m=20, azimuth_bins=180)
    expected = -np.rad2deg(np.arccos(lunar.MOON_RADIUS_M / (lunar.MOON_RADIUS_M + 20)))
    assert np.max(np.abs(h.horizon_elevation_deg - expected)) < 0.01


@pytest.mark.parametrize("height", [-1, np.nan, np.inf])
def test_invalid_horizon_height(height):
    with pytest.raises(ValueError):
        lunar.terrain_horizon(terrain(), site_x_m=0, site_y_m=0, tower_height_m=height)


def test_disc_visibility_boundaries():
    np.testing.assert_allclose(lunar.solar_disc_visibility([-1, 0, 1], 0, 1), [0, 0.5, 1])
    values = lunar.solar_disc_visibility(np.linspace(-1, 1, 21), 0, 1)
    np.testing.assert_allclose(values + values[::-1], 1)
    with pytest.raises(ValueError):
        lunar.solar_disc_visibility(0, 0, 0)


def test_sun_geometry_earth_eclipse_and_inverse_square():
    au = 149_597_870_700.0
    sun = np.array([[au, 0, 0], [2 * au, 0, 0]])
    earth = np.array([[-384_400_000.0, 0, 0]] * 2)
    g = lunar.lunar_solar_geometry(sun, earth, longitude_deg=0, latitude_deg=0, elevation_m=0)
    np.testing.assert_allclose(g.elevation_deg, 90)
    np.testing.assert_allclose(g.earth_visible_fraction, 1)
    assert g.unobstructed_dni_w_m2.iloc[0] / g.unobstructed_dni_w_m2.iloc[1] == pytest.approx(
        4, rel=3e-5
    )
    eclipsed = lunar.lunar_solar_geometry(
        sun, -earth, longitude_deg=0, latitude_deg=0, elevation_m=0
    )
    np.testing.assert_allclose(eclipsed.earth_visible_fraction, 0)


def test_fixed_tracking_and_darkness_pv():
    reference = PvwattsReference(300, -0.002, 1361)
    fixed = lunar.lunar_pv_power(
        geometry(), horizon(), tilt_deg=90, reference=reference, cell_temperature_c=25
    )
    assert fixed.dc_power_w.iloc[0] == pytest.approx(300 * np.cos(np.deg2rad(30)))
    tracked = lunar.lunar_pv_power(
        geometry(), horizon(), mode="sun_tracking", reference=reference, cell_temperature_c=25
    )
    assert tracked.dc_power_w.iloc[0] == pytest.approx(300)
    dark = lunar.lunar_pv_power(geometry(), horizon(40), reference=reference, cell_temperature_c=25)
    assert dark.dc_power_w.iloc[0] == 0
    half = lunar.lunar_pv_power(
        geometry(), horizon(30), mode="sun_tracking", reference=reference, cell_temperature_c=25
    )
    assert half.dc_power_w.iloc[0] == pytest.approx(150)
    with pytest.raises(ValueError, match="Retention"):
        lunar.lunar_pv_power(
            geometry(), horizon(), optical_retention=1.1, reference=reference, cell_temperature_c=25
        )


def test_thermal_ground_view_factor_and_energy_balance():
    ground, view, emissivity = 240, 0.4, 0.95
    equilibrium = (view * emissivity * ground**4 + (1 - view) * 3**4) ** 0.25
    result = lunar.lunar_panel_thermal(
        [0, 3600, 7200],
        0,
        ground_temperature_k=ground,
        ground_view_factor=view,
        ground_emissivity=emissivity,
        surface=physics.ThermalSurface(area_m2=2, radiating_area_m2=4),
        initial_temperature_k=equilibrium,
        max_step_s=600,
    )
    np.testing.assert_allclose(result.temperature_k, equilibrium, atol=1e-8)
    np.testing.assert_allclose(result.energy_balance_error_j, 0, atol=1e-6)
    np.testing.assert_allclose(
        lunar.survival_heater_power(
            [100, 300], setpoint_k=250, thermal_conductance_w_k=2, internal_heat_w=20
        ),
        [280, 0],
    )


def test_darkness_irregular_intervals_and_censoring():
    assert lunar.longest_darkness_hours([0, 600, 3000, 3600], [0, 0, 1]) == pytest.approx(
        3000 / 3600
    )
    assert lunar.longest_darkness_hours([0, 3600, 7200, 10800], [0, 1, 0]) == 1
    with pytest.raises(ValueError):
        lunar.longest_darkness_hours([0, 0, 1], [0, 1])


def test_storage_rejects_initial_charge_as_sustainable_supply():
    battery = physics.BatterySpec(1000, initial_soc=0.8, minimum_soc=0.1)
    result = lunar.size_lunar_storage(
        [0, 3600], [0], [10], array_areas_m2=[1], capacities_wh=[1000], battery_template=battery
    )
    assert result.unserved_energy_wh.iloc[0] == 0
    assert not result.feasible.iloc[0]
    result = lunar.size_lunar_storage(
        [0, 3600], [100], [10], array_areas_m2=[1], capacities_wh=[1000], battery_template=battery
    )
    assert result.feasible.iloc[0]
    limited = replace(battery, max_discharge_w=5)
    result = lunar.size_lunar_storage(
        [0, 3600],
        [0],
        [10],
        array_areas_m2=[1],
        capacities_wh=[1000],
        battery_template=limited,
        require_terminal_soc=False,
    )
    assert result.unserved_energy_wh.iloc[0] == pytest.approx(5)
    assert not result.feasible.iloc[0]


def test_rover_sunlit_detour_and_reserve():
    rover = lunar.LunarRover(
        mass_kg=10,
        rolling_resistance=0,
        speed_m_s=1,
        housekeeping_w=10,
        capacity_wh=25,
        initial_energy_wh=16,
        reserve_wh=5,
    )
    z = np.zeros((3, 5))
    power = np.zeros((8, 3, 5))
    power[:, 0, :] = 40
    result = lunar.energy_aware_route(
        z, np.arange(9) * 1800, power, cell_size_m=10, start=(1, 0), goal=(1, 4), rover=rover
    )
    assert 0 in result.row.values  # direct dark route cannot maintain the reserve
    assert result.energy_wh.min() >= rover.reserve_wh
    assert result.time_s.iloc[-1] > 4 * 1800
    with pytest.raises(ValueError, match="No energy-feasible"):
        lunar.energy_aware_route(
            z, np.arange(9) * 1800, 0, cell_size_m=10, start=(1, 0), goal=(1, 4), rover=rover
        )


def test_rover_speed_slopes_obstacles_and_start_goal():
    rover = lunar.LunarRover()
    z = np.zeros((2, 2))
    result = lunar.energy_aware_route(
        z, [0, 100], 0, cell_size_m=10, start=(0, 0), goal=(0, 0), rover=rover
    )
    assert len(result) == 1
    with pytest.raises(ValueError, match="No energy-feasible"):
        lunar.energy_aware_route(
            z, [0, 1], 0, cell_size_m=10, start=(0, 0), goal=(1, 1), rover=rover
        )
    z[0, 1], z[1, 0] = np.nan, 100
    with pytest.raises(ValueError, match="No energy-feasible"):
        lunar.energy_aware_route(
            z, [0, 10000, 20000], 0, cell_size_m=10, start=(0, 0), goal=(1, 1), rover=rover
        )
