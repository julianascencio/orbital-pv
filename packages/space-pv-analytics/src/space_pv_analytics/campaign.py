"""Bounded exact planning of proposed qualification requirement coverage."""

import itertools
import math

import pandas as pd


class InfeasibleCampaignError(ValueError):
    """No proposed test subset covers every mandatory requirement within budget."""


def plan_test_campaign(
    requirements: pd.DataFrame,
    tests: pd.DataFrame,
    coverage: pd.DataFrame,
    *,
    budget_h: float,
    mandatory_requirements: tuple[str, ...] = (),
) -> tuple[dict, pd.DataFrame]:
    """Maximize covered priority weight, then minimize hours and sorted test IDs.

    Requirements: requirement_id, mission_id, boundary, weight.
    Tests: test_id, mission_id, boundary, hours. Coverage: test_id, requirement_id.
    Every edge is a caller-reviewed PROPOSED coverage claim, not test evidence.
    Matching mission/boundary is necessary but does not validate protocols,
    severity, specimen independence, outcomes or certification. No partial
    test execution, precedence, parallelism or shared specimen costs modeled.
    Reject >18 tests (at most 262144 subsets). Weights are planning priorities,
    not probabilities. Uncovered requirements remain visible at any budget.
    Mandatory requirement IDs are hard constraints, never priority penalties.
    Raise InfeasibleCampaignError if no admissible subset covers them.
    Feasibility refers only to supplied coverage claims, not qualification.
    """
    for frame, cols, key in (
        (requirements, {"requirement_id", "mission_id", "boundary", "weight"}, "requirement_id"),
        (tests, {"test_id", "mission_id", "boundary", "hours"}, "test_id"),
    ):
        if frame.empty or not cols.issubset(frame.columns) or frame[key].duplicated().any():
            raise ValueError("Nonempty registries with required columns and unique IDs required")
        for col in (key, "mission_id", "boundary"):
            if not frame[col].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
                raise ValueError("Identifiers and boundary must be nonempty strings")
    if len(tests) > 18:
        raise ValueError("Exact planning limited to 18 tests")
    if not math.isfinite(budget_h) or budget_h < 0:
        raise ValueError("Budget must be finite and nonnegative")
    for values in (requirements.weight, tests.hours):
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError("Weights and hours must be finite and positive")
    if not {"test_id", "requirement_id"}.issubset(coverage.columns):
        raise ValueError("Coverage edge columns required")
    if coverage.duplicated(["test_id", "requirement_id"]).any():
        raise ValueError("Duplicate coverage edge")
    req = requirements.set_index("requirement_id")
    if (
        isinstance(mandatory_requirements, str)
        or not all(isinstance(key, str) and key in req.index for key in mandatory_requirements)
        or len(set(mandatory_requirements)) != len(mandatory_requirements)
    ):
        raise ValueError("Mandatory IDs must be unique known requirement IDs")
    mandatory = set(mandatory_requirements)
    test = tests.set_index("test_id")
    edges = {key: set() for key in test.index}
    for test_id, requirement_id in coverage[["test_id", "requirement_id"]].itertuples(
        index=False, name=None
    ):
        if test_id not in test.index or requirement_id not in req.index:
            raise ValueError("Coverage references unknown ID")
        a, b = test.loc[test_id], req.loc[requirement_id]
        if a.mission_id != b.mission_id or a.boundary != b.boundary:
            raise ValueError("Coverage cannot transfer across missions or hardware boundaries")
        edges[test_id].add(requirement_id)
    ids = sorted(test.index)
    best_key = (math.inf, math.inf, ()) if mandatory else (0.0, 0.0, ())
    best_ids, best_covered = (), set()
    for count in range(1, len(ids) + 1):
        for chosen in itertools.combinations(ids, count):
            hours = math.fsum(test.loc[key, "hours"] for key in chosen)
            if hours > budget_h:
                continue
            covered = set().union(*(edges[key] for key in chosen))
            if not mandatory.issubset(covered):
                continue
            score = math.fsum(req.loc[key, "weight"] for key in sorted(covered))
            key = (-score, hours, chosen)
            if key < best_key:
                best_key, best_ids, best_covered = key, chosen, covered
    if math.isinf(best_key[0]):
        raise InfeasibleCampaignError("Mandatory coverage is infeasible at this budget")
    result = {
        "mandatory_requirements": sorted(mandatory),
        "selected_tests": list(best_ids),
        "planned_hours": best_key[1],
        "covered_weight": -best_key[0],
        "total_weight": float(req.weight.sum()),
        "budget_h": budget_h,
        "all_requirements_planned": len(best_covered) == len(req),
        "qualification_demonstrated": False,
    }
    matrix = requirements.copy()
    matrix["mandatory"] = matrix.requirement_id.isin(mandatory)
    matrix["planned_coverage"] = matrix.requirement_id.isin(best_covered)
    matrix["selected_supporting_tests"] = matrix.requirement_id.map(
        lambda requirement: ";".join(key for key in best_ids if requirement in edges[key])
    )
    return result, matrix
