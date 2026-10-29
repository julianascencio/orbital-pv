import pytest

from space_pv_core.constants import ASTRONOMICAL_UNIT_M, SOLAR_CONSTANT_W_M2
from space_pv_space_env import am0_irradiance, incidence_factor


def test_am0_at_one_au() -> None:
    assert am0_irradiance(ASTRONOMICAL_UNIT_M) == pytest.approx(SOLAR_CONSTANT_W_M2)


def test_incidence_factor_clips_and_eclipse() -> None:
    assert incidence_factor(0.5, True) == pytest.approx(0.5)
    assert incidence_factor(-0.2, True) == 0.0
    assert incidence_factor(0.9, False) == 0.0
