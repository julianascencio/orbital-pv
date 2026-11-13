from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from orbitalpv.orbit import circular_orbit_period_s
from orbitalpv.space_ai import (
    FormationSpec,
    OpticalLinkSpec,
    confocal_spatial_geometry,
    formation_metrics,
    hcw_formation,
    launch_energy_cost_parity,
    launch_learning_price,
    launched_power_cost,
    load_space_ai_evidence,
    optical_link_budget,
    radiation_event_screen,
)
from orbitalpv.space_ai_analysis import space_ai_trade_study


def test_optical_reference_and_inverse_square():
    frame = optical_link_budget([2_500_000, 5_000_000])
    # Paper Section 4.2 gives ~1.6 uW at 5000 km; recomputed from aperture efficiency.
    assert frame.received_power_w.iloc[1] == pytest.approx(1.6e-6, rel=0.04)
    assert frame.received_power_w.iloc[0] / frame.received_power_w.iloc[1] == pytest.approx(4)
    assert frame.one_way_propagation_us.iloc[1] == pytest.approx(16678.20476)
    assert not frame.full_rate_screen_pass.any()


def test_optical_caps_and_photon_energy_scaling():
    frame = optical_link_budget([20_000, 300_000, 5_000_000])
    assert frame.full_rate_screen_pass.iloc[0]
    assert frame.screened_rate_gbps.iloc[0] == 9600
    assert (frame.received_power_w <= 5).all()
    assert (frame.screened_rate_gbps <= frame.photon_ceiling_gbps).all()
    low_power = optical_link_budget([300_000], replace(OpticalLinkSpec(), transmit_power_w=2.5))
    assert low_power.received_power_w.iloc[0] == pytest.approx(frame.received_power_w.iloc[1] / 2)
    assert low_power.full_rate_margin_db.iloc[0] == pytest.approx(
        frame.full_rate_margin_db.iloc[1] - 3.0102999566
    )
    # Additional channels do not create photons or transmitted power.
    more_channels = optical_link_budget([5_000_000], replace(OpticalLinkSpec(), channels=48))
    assert more_channels.photon_ceiling_gbps.iloc[0] == pytest.approx(
        frame.photon_ceiling_gbps.iloc[2]
    )


@pytest.mark.parametrize(
    "distance", [[], [0], [-1], [5000], [float("nan")], [float("inf")], [[20000]]]
)
def test_optical_rejects_invalid_or_near_field_distance(distance):
    with pytest.raises(ValueError):
        optical_link_budget(distance)


@pytest.mark.parametrize(
    "changes",
    [
        {"channels": True},
        {"channels": 0},
        {"aperture_efficiency": 1.1},
        {"loss_db": -1},
        {"photons_per_bit": 0},
        {"transmit_power_w": float("nan")},
    ],
)
def test_optical_rejects_invalid_specs(changes):
    with pytest.raises(ValueError):
        replace(OpticalLinkSpec(), **changes)


def test_confocal_reference_geometry():
    one, two, four = [confocal_spatial_geometry(beams_per_axis=n) for n in (1, 2, 4)]
    assert one["ideal_distance_m"] == pytest.approx(5067.084925)
    assert two["ideal_distance_m"] == pytest.approx(one["ideal_distance_m"] / 4)
    assert four["ideal_distance_m"] == pytest.approx(316.692808)
    assert one["pointing_allowance_urad"] == pytest.approx(0.98676065)
    assert four["beam_count"] == 16
    # This function deliberately reports geometry, not an unvalidated data rate.
    assert not any("gbps" in key for key in four)


def test_hcw_periodicity_radius_and_dynamics():
    spec = FormationSpec()
    period = circular_orbit_period_s(spec.altitude_m)
    time = np.linspace(0, period, 121)
    states = hcw_formation(time, spec)
    assert states.shape == (121, 81, 6)
    np.testing.assert_allclose(states[0], states[-1], atol=1e-10)
    assert np.linalg.norm(states[..., :3], axis=-1).max() == pytest.approx(1000)
    np.testing.assert_allclose(states[:, 40], 0, atol=1e-12)
    # Independent finite differences verify both velocity and HCW acceleration equations.
    dt = 0.1
    mid = hcw_formation([1234], spec)[0]
    before, after = hcw_formation([1234 - dt, 1234 + dt], spec)
    np.testing.assert_allclose((after[:, :3] - before[:, :3]) / (2 * dt), mid[:, 3:], atol=1e-8)
    acceleration = (after[:, 3:] - before[:, 3:]) / (2 * dt)
    n = 2 * np.pi / period
    np.testing.assert_allclose(
        acceleration[:, 0], 2 * n * mid[:, 4] + 3 * n * n * mid[:, 0], atol=1e-9
    )
    np.testing.assert_allclose(acceleration[:, 1], -2 * n * mid[:, 3], atol=1e-9)
    metrics = formation_metrics(time, spec)
    assert metrics.sampled_min_separation_m.min() == pytest.approx(88.38834765)
    assert metrics.neighbor_max_m.max() == pytest.approx(176.7766953)
    assert (metrics.neighbor_max_one_way_us < 0.6).all()


@pytest.mark.parametrize(
    "changes",
    [
        {"grid_side": 2},
        {"grid_side": 8},
        {"grid_side": True},
        {"grid_side": 33},
        {"cluster_radius_m": 100000},
        {"altitude_m": float("nan")},
    ],
)
def test_formation_rejects_invalid_specs(changes):
    with pytest.raises(ValueError):
        replace(FormationSpec(), **changes)


def test_radiation_single_and_cluster_scaling():
    args = dict(annual_dose_rad_si=150, dose_per_event_rad_si=17, mission_years=5)
    single = radiation_event_screen(**args)
    fleet = radiation_event_screen(**args, device_count=81)
    assert single["mission_dose_rad_si"] == 750
    assert single["events_per_device_year"] == pytest.approx(8.8235294118)
    assert single["expected_events_per_inference"] == pytest.approx(2.796e-7, rel=0.001)
    assert fleet["expected_fleet_mission_events"] == pytest.approx(3573.5294118)
    assert fleet["expected_events_per_inference"] == single["expected_events_per_inference"]
    zero = radiation_event_screen(**{**args, "annual_dose_rad_si": 0})
    assert zero["probability_at_least_one_fleet_event"] == 0
    rare = radiation_event_screen(
        annual_dose_rad_si=1e-12, dose_per_event_rad_si=17, mission_years=5
    )
    assert rare["probability_at_least_one_fleet_event"] > 0


@pytest.mark.parametrize(
    "changes",
    [
        {"dose_per_event_rad_si": 0},
        {"annual_dose_rad_si": -1},
        {"mission_years": float("nan")},
        {"device_count": True},
        {"inferences_per_second_per_device": 0},
    ],
)
def test_radiation_rejects_invalid_inputs(changes):
    with pytest.raises(ValueError):
        radiation_event_screen(
            **{**dict(annual_dose_rad_si=150, dose_per_event_rad_si=17, mission_years=5), **changes}
        )


def test_launch_cost_hand_calculation_and_learning():
    assert (
        launched_power_cost(mass_kg=150, power_kw=0.8, lifetime_years=5, launch_price_usd_kg=200)
        == 7500
    )
    args = dict(initial_price_usd_kg=1800, initial_cumulative_mass_t=400, learning_rate=0.2)
    assert launch_learning_price(**args, cumulative_mass_t=400) == 1800
    assert launch_learning_price(**args, cumulative_mass_t=800) == 1440
    assert launch_learning_price(**args, cumulative_mass_t=370400) == pytest.approx(200, rel=0.01)
    parity = launch_energy_cost_parity(
        mass_kg=1000,
        continuous_compute_kw=100,
        lifetime_years=5,
        electricity_usd_kwh=0.1,
        terrestrial_pue=1.2,
        utilization=0.8,
    )
    assert parity == pytest.approx(420.48)
    assert launched_power_cost(
        mass_kg=1000, power_kw=100, lifetime_years=5, launch_price_usd_kg=parity
    ) == pytest.approx(840.96)
    for rate in (-0.1, 1, float("nan")):
        with pytest.raises(ValueError):
            launch_learning_price(**{**args, "learning_rate": rate}, cumulative_mass_t=800)
    with pytest.raises(ValueError):
        launch_learning_price(**args, cumulative_mass_t=399)


def test_pinned_evidence_and_end_to_end_study(tmp_path):
    evidence = load_space_ai_evidence()
    assert evidence["source"]["paper_id"] == "2511.19468v2"
    assert len(evidence["source"]["uploaded_pdf_sha256"]) == 64
    result = space_ai_trade_study(evidence)
    assert len(result) == 9
    assert result["solar_estimate"].paper_array_estimate_kw.iloc[0] == pytest.approx(28.29519)
    reference = result["launched_power"].iloc[0]
    assert reference.paper_reported_usd_kw_year == 810
    assert reference.calculated_usd_kw_year == pytest.approx(821.4285714)
    assert reference.difference_percent > 1
    screens = result["compute_screen"].set_index("scenario")
    assert screens.loc["High beta", "sustainable_compute_kw"] == 20
    assert screens.loc["Low beta eclipse", "sustainable_compute_kw"] < 10
    assert screens.loc["Half radiator area", "sustainable_compute_kw"] < 20
    assert screens.loc["25 percent PV loss", "sustainable_compute_kw"] < 20
    assert result["tid_context"].hbm_onset_to_mission_dose_ratio.iloc[0] == pytest.approx(8 / 3)
    evidence["source"]["paper_id"] = "2511.19468v1"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="pinned"):
        load_space_ai_evidence(path)
