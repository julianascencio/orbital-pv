import numpy as np
import pandas as pd
import pytest
from scipy.stats import beta

from orbitalpv.qualification import (
    deployment_reliability_lower_bound,
    summarize_deployment_trials,
    zero_failure_sample_size,
)


@pytest.mark.parametrize("s,f", [(1, 0), (20, 0), (19, 1), (50, 7), (1, 30), (300, 2), (0, 10)])
@pytest.mark.parametrize("confidence", [0.8, 0.95, 0.99])
def test_independent_beta_quantile_oracle(s, f, confidence):
    expected = 0 if s == 0 else beta.ppf(1 - confidence, s, f + 1)
    assert deployment_reliability_lower_bound(s, f, confidence=confidence) == pytest.approx(
        expected, abs=1e-12
    )


@pytest.mark.parametrize(
    "r,c,n", [(0.95, 0.95, 59), (0.99, 0.95, 299), (0.999, 0.95, 2995), (0.5, 0.5, 1)]
)
def test_plan_is_minimal(r, c, n):
    assert zero_failure_sample_size(r, confidence=c) == n
    assert deployment_reliability_lower_bound(n, 0, confidence=c) >= r
    if n > 1:
        assert deployment_reliability_lower_bound(n - 1, 0, confidence=c) < r


def test_registry_separates_protocols_and_rejects_repeated_hardware():
    data = pd.DataFrame(
        {
            "unit_id": ["a", "b", "c"],
            "design_id": ["v1"] * 3,
            "protocol_id": ["ambient", "ambient", "vacuum"],
            "success": [1, 0, 1],
        }
    )
    result = summarize_deployment_trials(data)
    assert result.units.tolist() == [2, 1]
    assert result.failures.tolist() == [1, 0]
    with pytest.raises(ValueError, match="Repeated hardware"):
        summarize_deployment_trials(pd.concat([data, data.iloc[:1]]))
    data.loc[0, "success"] = np.nan
    with pytest.raises(ValueError, match="binary"):
        summarize_deployment_trials(data)


@pytest.mark.parametrize("s,f", [(0, 0), (-1, 1), (1.5, 2), (True, 0)])
def test_invalid_counts(s, f):
    with pytest.raises(ValueError):
        deployment_reliability_lower_bound(s, f)


@pytest.mark.parametrize("p", [0, 1, -1, np.nan, np.inf])
def test_invalid_probabilities(p):
    with pytest.raises(ValueError):
        zero_failure_sample_size(p)
    with pytest.raises(ValueError):
        deployment_reliability_lower_bound(20, 1, confidence=p)
