import pandas as pd
import pytest

from orbitalpv.stress import combined_stress_interaction


def samples(combined=0.72):
    return pd.DataFrame(
        [
            {
                "sample_id": f"{arm}{i}",
                "campaign_id": "one",
                "arm": arm,
                "before_power_w": 1.0,
                "after_power_w": r,
            }
            for arm, r in [
                ("control", 1),
                ("radiation", 0.9),
                ("thermal", 0.8),
                ("combined", combined),
            ]
            for i in range(3)
        ]
    )


def test_multiplicative_null_and_pair_scaling():
    data = samples()
    result, arms = combined_stress_interaction(data, bootstrap_samples=100)
    assert result["interaction_ratio"] == pytest.approx(1)
    assert result["ratio_lower"] == pytest.approx(1)
    assert not result["extra_loss_supported"]
    assert arms.samples.sum() == 12
    data[["before_power_w", "after_power_w"]] *= 100
    scaled, _ = combined_stress_interaction(data, bootstrap_samples=100)
    assert scaled["interaction_ratio"] == pytest.approx(1)


def test_known_interaction_and_control_correction():
    data = samples(0.6)
    data.loc[data.arm == "control", "after_power_w"] = 0.98
    result, _ = combined_stress_interaction(data, bootstrap_samples=100)
    assert result["independent_retention"] == pytest.approx(0.9 * 0.8 / 0.98)
    assert result["interaction_ratio"] == pytest.approx(0.6 * 0.98 / (0.9 * 0.8))
    assert result["extra_loss_supported"]


@pytest.mark.parametrize("change", ["duplicate", "missing_arm", "small", "power", "campaign"])
def test_reject_invalid_registry(change):
    data = samples()
    if change == "duplicate":
        data.loc[1, "sample_id"] = data.loc[0, "sample_id"]
    if change == "missing_arm":
        data = data[data.arm != "control"]
    if change == "small":
        data = data.iloc[1:]
    if change == "power":
        data.loc[0, "after_power_w"] = 0
    if change == "campaign":
        data.loc[0, "campaign_id"] = "two"
    with pytest.raises(ValueError):
        combined_stress_interaction(data, bootstrap_samples=100)


def test_seed_reproducibility_and_variance():
    data = samples()
    data.loc[0, "after_power_w"] *= 0.95
    a, _ = combined_stress_interaction(data, bootstrap_samples=100, seed=4)
    b, _ = combined_stress_interaction(data, bootstrap_samples=100, seed=4)
    assert a == b
    assert a["ratio_lower"] < a["ratio_upper"]
