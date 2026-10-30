from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from space_pv_pvmodel.losses import pvwatts_loss_chain
from space_pv_pvmodel.model import PvwattsReference, pvwatts_dc_space

REFERENCE = PvwattsReference(100.0, -0.01, reference_irradiance_w_m2=1000.0)
STAGE_COLUMNS = [
    "reference_power_w",
    "after_irradiance_w",
    "after_eclipse_w",
    "after_pointing_w",
    "after_spectral_w",
    "after_optical_w",
    "after_temperature_w",
    "after_degradation_w",
    "after_mismatch_w",
    "after_wiring_w",
    "after_conversion_w",
    "after_clipping_w",
    "after_availability_w",
    "modeled_power_w",
]
FRACTION_INPUTS = [
    "illumination_fraction",
    "cosine_aoi",
    "optical_factor",
    "degradation_factor",
    "mismatch_factor",
    "wiring_efficiency",
    "conversion_efficiency",
    "availability_factor",
    "curtailment_factor",
]


def test_manual_loss_and_gain_budget_and_electronics_order():
    result = pvwatts_loss_chain(
        REFERENCE,
        am0_irradiance_w_m2=800.0,
        illumination_fraction=0.5,
        cosine_aoi=0.8,
        spectral_factor=1.1,
        optical_factor=0.9,
        cell_temperature_c=15.0,
        degradation_factor=0.95,
        mismatch_factor=0.97,
        wiring_efficiency=0.98,
        conversion_efficiency=0.9,
        power_limit_w=20.0,
        availability_factor=0.8,
        curtailment_factor=0.75,
    )
    assert list(result.columns) == STAGE_COLUMNS
    assert result.index.equals(pd.RangeIndex(1))
    np.testing.assert_allclose(
        result.iloc[0],
        [
            100,
            80,
            40,
            32,
            35.2,
            31.68,
            34.848,
            33.1056,
            32.112432,
            31.47018336,
            28.323165024,
            20,
            16,
            12,
        ],
    )


def test_temperature_stage_matches_existing_pvwatts_model():
    reference = PvwattsReference(500.0, -0.003)
    am0 = np.array([1361.0, 900.0, 1500.0, 0.0])
    illumination = np.array([1.0, 0.5, 0.0, 1.0])
    cosine = np.array([0.8, 0.9, 1.0, 0.0])
    temperature = np.array([60.0, -10.0, 25.0, 40.0])
    result = pvwatts_loss_chain(
        reference,
        am0_irradiance_w_m2=am0,
        illumination_fraction=illumination,
        cosine_aoi=cosine,
        spectral_factor=1.02,
        optical_factor=0.97,
        cell_temperature_c=temperature,
    )
    expected = pvwatts_dc_space(am0 * illumination * cosine * 1.02 * 0.97, temperature, reference)
    np.testing.assert_array_equal(result["after_temperature_w"], expected)
    np.testing.assert_array_equal(result["modeled_power_w"], expected)


def test_broadcast_zero_eclipse_and_per_sample_power_caps():
    result = pvwatts_loss_chain(
        REFERENCE,
        am0_irradiance_w_m2=[1000.0],
        illumination_fraction=[1.0, 0.0, 0.5],
        power_limit_w=[80.0, 80.0, 20.0],
        availability_factor=[0.5],
    )
    np.testing.assert_allclose(result["after_conversion_w"], [100.0, 0.0, 50.0])
    np.testing.assert_allclose(result["modeled_power_w"], [40.0, 0.0, 10.0])


def test_zero_reference_irradiance_input_and_thermal_factor_are_valid():
    zero_reference = pvwatts_loss_chain(replace(REFERENCE, pdc0_w=0.0))
    assert (zero_reference.to_numpy() == 0.0).all()
    dark = pvwatts_loss_chain(REFERENCE, am0_irradiance_w_m2=0.0)
    assert (dark.iloc[:, 1:].to_numpy() == 0.0).all()
    zero_thermal = pvwatts_loss_chain(REFERENCE, cell_temperature_c=125.0)
    assert zero_thermal["modeled_power_w"].iloc[0] == 0.0


def test_shared_series_index_is_preserved_without_alignment_or_input_mutation():
    index = pd.Index(["b", "a", "c"], name="sample")
    illumination = pd.Series([1.0, 0.5, 0.0], index=index)
    temperature = pd.Series([25.0, 15.0, 50.0], index=index)
    before = illumination.copy()
    result = pvwatts_loss_chain(
        REFERENCE,
        am0_irradiance_w_m2=1000.0,
        illumination_fraction=illumination,
        cell_temperature_c=temperature,
        optical_factor=np.array([0.9, 0.8, 0.7]),
    )
    pd.testing.assert_index_equal(result.index, index)
    pd.testing.assert_series_equal(illumination, before)
    np.testing.assert_allclose(result["modeled_power_w"], [90.0, 44.0, 0.0])


def test_differently_ordered_series_indexes_are_rejected():
    with pytest.raises(ValueError, match="identical indexes"):
        pvwatts_loss_chain(
            REFERENCE,
            illumination_fraction=pd.Series([1.0, 0.5], index=["a", "b"]),
            cell_temperature_c=pd.Series([25.0, 30.0], index=["b", "a"]),
        )


def test_indexed_single_row_is_not_broadcast_over_unindexed_samples():
    with pytest.raises(ValueError, match="index must match"):
        pvwatts_loss_chain(
            REFERENCE,
            illumination_fraction=pd.Series([1.0], index=["a"]),
            cell_temperature_c=[25.0, 30.0],
        )


@pytest.mark.parametrize("value", [[], [[1.0, 0.5]], [[1.0], [0.5]]])
def test_empty_inputs_and_matrices_are_rejected(value):
    with pytest.raises(ValueError, match="nonempty one-dimensional"):
        pvwatts_loss_chain(REFERENCE, illumination_fraction=value)


def test_incompatible_sample_counts_are_rejected():
    with pytest.raises(ValueError, match="common one-dimensional sample count"):
        pvwatts_loss_chain(
            REFERENCE, illumination_fraction=[1.0, 0.5], cell_temperature_c=[20, 25, 30]
        )


@pytest.mark.parametrize("name", FRACTION_INPUTS)
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_fraction_domains_are_validated_without_silent_clipping(name, value):
    with pytest.raises(ValueError, match=name):
        pvwatts_loss_chain(REFERENCE, **{name: value})


@pytest.mark.parametrize(
    "name",
    [
        *FRACTION_INPUTS,
        "am0_irradiance_w_m2",
        "spectral_factor",
        "cell_temperature_c",
        "power_limit_w",
    ],
)
@pytest.mark.parametrize("value", [np.nan, np.inf])
def test_all_inputs_must_be_finite(name, value):
    with pytest.raises(ValueError, match=name):
        pvwatts_loss_chain(REFERENCE, **{name: [1.0, value]})


def test_nullable_series_missing_values_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        pvwatts_loss_chain(
            REFERENCE, illumination_fraction=pd.Series([1.0, pd.NA], dtype="Float64")
        )


@pytest.mark.parametrize(
    ("name", "value"),
    [("am0_irradiance_w_m2", -1.0), ("spectral_factor", 0.0), ("power_limit_w", -1.0)],
)
def test_irradiance_spectral_and_cap_domains(name, value):
    with pytest.raises(ValueError, match=name):
        pvwatts_loss_chain(REFERENCE, **{name: value})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("pdc0_w", -1.0),
        ("pdc0_w", np.nan),
        ("reference_irradiance_w_m2", 0.0),
        ("reference_irradiance_w_m2", -100.0),
        ("reference_irradiance_w_m2", np.inf),
        ("gamma_pdc_per_c", np.nan),
        ("reference_temperature_c", np.inf),
        ("pdc0_w", [100.0]),
    ],
)
def test_reference_calibration_is_validated(name, value):
    with pytest.raises(ValueError, match=name):
        pvwatts_loss_chain(replace(REFERENCE, **{name: value}))


def test_negative_thermal_factor_is_rejected_even_in_eclipse():
    with pytest.raises(ValueError, match="temperature multiplier"):
        pvwatts_loss_chain(REFERENCE, illumination_fraction=0.0, cell_temperature_c=126.0)


def test_real_inputs_cannot_silently_overflow_into_stage_powers():
    with pytest.raises(ValueError, match="nonfinite stage power"):
        pvwatts_loss_chain(REFERENCE, am0_irradiance_w_m2=1e308, spectral_factor=1e308)


def test_complex_input_is_not_cast_to_its_real_component():
    with pytest.raises(ValueError, match="real numeric"):
        pvwatts_loss_chain(REFERENCE, illumination_fraction=np.array([0.5 + 0.1j]))


@pytest.mark.parametrize(
    "value",
    [
        np.array([np.complex128(0.5 + 0.1j)], dtype=object),
        pd.Series([np.complex128(0.5 + 0.1j)], dtype=object),
    ],
)
def test_object_dtype_complex_input_cannot_discard_its_imaginary_component(value):
    with pytest.raises(ValueError, match="real numeric"):
        pvwatts_loss_chain(REFERENCE, illumination_fraction=value)
