import numpy as np
import pytest

import orbitalpv as opv


def test_five_space_cell_technologies_are_available() -> None:
    technologies = opv.list_space_cell_technologies()
    assert len(technologies) == 5
    assert {technology.slug for technology in technologies} == {
        "silicon",
        "gaas",
        "triple_junction",
        "four_junction",
        "imm",
    }


@pytest.mark.parametrize(
    "slug, expected_efficiency",
    [
        ("silicon", 0.168),
        ("gaas", 0.19),
        ("triple_junction", 0.295),
        ("four_junction", 0.315),
        ("imm", 0.32),
    ],
)
def test_reference_space_cell_efficiency_is_close_to_template(
    slug: str,
    expected_efficiency: float,
) -> None:
    result = opv.simulate_space_cell(slug, points=4001)
    assert result.efficiency == pytest.approx(expected_efficiency, abs=0.012)
    assert result.pmp_w_m2 > 0.0
    assert result.vmp_v > 0.0
    assert result.imp_ma_cm2 > 0.0


def test_space_cell_power_falls_with_high_temperature_and_radiation() -> None:
    bol = opv.simulate_space_cell("triple_junction")
    hot = opv.simulate_space_cell("triple_junction", cell_temperature_c=100.0)
    irradiated = opv.simulate_space_cell(
        "triple_junction",
        fluence_1mev_e_cm2=1.0e15,
    )
    assert hot.pmp_w_m2 < bol.pmp_w_m2
    assert irradiated.pmp_w_m2 < bol.pmp_w_m2
    assert irradiated.radiation_factor == pytest.approx(0.84)


def test_space_cell_zero_irradiance_returns_zero_power() -> None:
    result = opv.simulate_space_cell("imm", irradiance_w_m2=0.0)
    assert result.pmp_w_m2 == 0.0
    assert result.efficiency == 0.0
    assert np.all(result.power_density_w_m2 == 0.0)


def test_space_cell_aliases() -> None:
    assert opv.get_space_cell_technology("3J").slug == "triple_junction"
    assert opv.get_space_cell_technology("c-Si").slug == "silicon"
