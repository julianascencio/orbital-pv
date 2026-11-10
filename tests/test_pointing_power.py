import importlib.util
from pathlib import Path

import numpy as np
import pytest

from orbitalpv.physics import pointing_power_envelope


def test_analytic_threshold_and_infeasible_states():
    result = pointing_power_envelope([0, 99, 100, 200], 100, reserve_fraction=0, offpoint_deg=0)
    np.testing.assert_array_equal(result.normal_feasible, [False, False, True, True])
    assert result.max_offpoint_deg.iloc[:2].isna().all()
    np.testing.assert_allclose(result.max_offpoint_deg.iloc[2:], [0, 60])
    np.testing.assert_allclose(result.headroom_w, [-100, -1, 0, 100])


def test_reserve_is_relative_to_load_and_grazing_power_is_zero():
    result = pointing_power_envelope(120, 100, reserve_fraction=0.2, offpoint_deg=90)
    assert result.required_bus_w.iloc[0] == 120
    assert result.normal_feasible.iloc[0]
    assert not result.offpoint_feasible.iloc[0]
    assert result.headroom_w.iloc[0] == -120


def test_cosine_power_and_monotonic_limits():
    result = pointing_power_envelope([200, 400], 100, reserve_fraction=0, offpoint_deg=60)
    np.testing.assert_allclose(result.offpoint_bus_w, [100, 200])
    assert result.max_offpoint_deg.iloc[1] > result.max_offpoint_deg.iloc[0]
    tighter = pointing_power_envelope([200, 400], 100, reserve_fraction=0.2)
    assert (tighter.max_offpoint_deg < result.max_offpoint_deg).all()


@pytest.mark.parametrize("normal", [[], [[100]], [-1], [np.nan], [np.inf]])
def test_invalid_power(normal):
    with pytest.raises(ValueError):
        pointing_power_envelope(normal, 100)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"load_w": 0},
        {"load_w": -1},
        {"load_w": np.inf},
        {"reserve_fraction": -0.1},
        {"reserve_fraction": np.nan},
        {"offpoint_deg": -1},
        {"offpoint_deg": 91},
        {"offpoint_deg": np.nan},
    ],
)
def test_invalid_constraints(kwargs):
    with pytest.raises(ValueError):
        pointing_power_envelope(100, **{"load_w": 100, **kwargs})


def test_mars_study_reproduction_and_required_rating():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "pointing_example", root / "examples/space_business/plot_mars_pointing.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frame, sensitivity = module.study()
    assert len(frame) == 732
    assert len(sensitivity) == 36
    assert 1.38 < frame.sun_distance_au.min() < 1.39
    assert 1.66 < frame.sun_distance_au.max() < 1.67
    assert frame.normal_feasible.all()
    assert (~frame.offpoint_feasible).sum() == 108
    # Independent inverse-square/cosine budget and inverse sizing identity.
    expected = 1400 * 0.9 * 0.9 / frame.sun_distance_au**2 * np.cos(np.pi / 6)
    np.testing.assert_allclose(frame.offpoint_bus_w, expected)
    resized = frame.required_array_1au_w.max() / 1400 * frame.offpoint_bus_w
    assert resized.min() == pytest.approx(360)
    assert (
        sensitivity[sensitivity.array_1au_w == 1600].minimum_headroom_w.to_numpy()
        > sensitivity[sensitivity.array_1au_w == 1000].minimum_headroom_w.to_numpy()
    ).all()
