import numpy as np
import pandas as pd
import pytest

from orbitalpv.recovery import recovery_history


def history(rows):
    return pd.DataFrame(rows, columns=["duration_h", "damage_rate_h_inv", "recovery_rate_h_inv"])


def test_damage_only_and_exact_mean():
    out = recovery_history(history([[2, 0.1, 0]]))
    assert out.end_retention.iloc[0] == pytest.approx(np.exp(-0.2))
    assert out.mean_retention.iloc[0] == pytest.approx(-np.expm1(-0.2) / 0.2)


def test_recovery_and_permanent_floor():
    out = recovery_history(history([[3, 0, 0.2]]), initial_deficit=0.5, permanent_retention=0.9)
    assert out.end_retention.iloc[0] == pytest.approx(0.9 * (1 - 0.5 * np.exp(-0.6)))
    assert out.minimum_retention.iloc[0] == pytest.approx(0.45)


def test_subdivision_invariance_and_equilibrium():
    whole = recovery_history(history([[10, 0.1, 0.2]]))
    split = recovery_history(history([[1, 0.1, 0.2]] * 10))
    assert split.end_retention.iloc[-1] == pytest.approx(whole.end_retention.iloc[-1])
    assert split.mean_retention.mean() == pytest.approx(whole.mean_retention.iloc[0])
    equilibrium = recovery_history(history([[10, 0.1, 0.2]]), initial_deficit=1 / 3)
    assert equilibrium.end_retention.iloc[0] == pytest.approx(2 / 3)


def test_zero_rates_preserve_state():
    out = recovery_history(history([[3, 0, 0]]), initial_deficit=0.2)
    assert out.mean_retention.iloc[0] == pytest.approx(0.8)


@pytest.mark.parametrize("row", [[0, 0, 0], [1, -1, 0], [1, 0, np.nan]])
def test_invalid(row):
    with pytest.raises(ValueError):
        recovery_history(history([row]))
