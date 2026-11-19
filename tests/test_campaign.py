import pandas as pd
import pytest

from orbitalpv.campaign import plan_test_campaign


def inputs():
    req = pd.DataFrame(
        {
            "requirement_id": ["a", "b"],
            "mission_id": ["m"] * 2,
            "boundary": ["panel"] * 2,
            "weight": [1, 2],
        }
    )
    tests = pd.DataFrame(
        {
            "test_id": ["x", "y", "z"],
            "mission_id": ["m"] * 3,
            "boundary": ["panel"] * 3,
            "hours": [2, 2, 3],
        }
    )
    edges = pd.DataFrame({"test_id": ["x", "y", "z", "z"], "requirement_id": ["a", "b", "a", "b"]})
    return req, tests, edges


def test_exact_plan_and_priority():
    req, tests, edges = inputs()
    plan, matrix = plan_test_campaign(req, tests, edges, budget_h=3)
    assert plan["selected_tests"] == ["z"]
    assert matrix.planned_coverage.all()
    assert not plan["qualification_demonstrated"]
    plan, _ = plan_test_campaign(req, tests, edges, budget_h=2)
    assert plan["selected_tests"] == ["y"]


def test_empty_plan_and_permutation_invariance():
    req, tests, edges = inputs()
    plan, _ = plan_test_campaign(req, tests, edges, budget_h=0)
    assert plan["selected_tests"] == []
    assert plan["covered_weight"] == 0
    a, _ = plan_test_campaign(req, tests, edges, budget_h=4)
    b, _ = plan_test_campaign(req.iloc[::-1], tests.iloc[::-1], edges.iloc[::-1], budget_h=4)
    assert a == b


@pytest.mark.parametrize(
    "problem", ["boundary", "mission_id", "unknown", "duplicate", "cost", "budget"]
)
def test_reject_invalid(problem):
    req, tests, edges = inputs()
    budget = 4
    if problem in ("boundary", "mission_id"):
        tests.loc[0, problem] = "different"
    elif problem == "unknown":
        edges.loc[0, "requirement_id"] = "unknown"
    elif problem == "duplicate":
        edges = pd.concat([edges, edges.iloc[:1]])
    elif problem == "cost":
        tests.loc[0, "hours"] = -1
    else:
        budget = float("nan")
    with pytest.raises(ValueError):
        plan_test_campaign(req, tests, edges, budget_h=budget)
