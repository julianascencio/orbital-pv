"""
Plan laboratory hours without claiming qualification
====================================================

DOE workshop recommendations motivate mission-specific qualification planning.
All requirements, coverage links, weights and lab hours here are synthetic.
Selected tests remain proposals: none is represented as completed evidence.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from orbitalpv.campaign import InfeasibleCampaignError, plan_test_campaign
from orbitalpv.data import load_table


def study():
    root = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    req, tests, edges = [
        load_table(root / "_data" / f"campaign_{name}.csv")
        for name in ("requirements", "tests", "coverage")
    ]
    rows = []
    for policy, mandatory in (("weighted only", ()), ("deployment mandatory", ("deployment",))):
        for budget in range(11):
            try:
                result, _ = plan_test_campaign(
                    req, tests, edges, budget_h=budget, mandatory_requirements=mandatory
                )
                rows.append({**result, "policy": policy, "feasible": True})
            except InfeasibleCampaignError:
                # Missing objective, not zero coverage: there is no admissible plan.
                rows.append(
                    {
                        "budget_h": budget,
                        "policy": policy,
                        "feasible": False,
                        "covered_weight": float("nan"),
                    }
                )
    result, matrix = plan_test_campaign(req, tests, edges, budget_h=8)
    # Sensitivity: withdraw a coverage claim; never silently assume equivalence.
    reduced = edges[~((edges.test_id == "combined-rt") & (edges.requirement_id == "thermal"))]
    sensitivity, _ = plan_test_campaign(req, tests, reduced, budget_h=8)
    mandatory_plan, mandatory_matrix = plan_test_campaign(
        req, tests, reduced, budget_h=8, mandatory_requirements=("deployment",)
    )
    sensitivity = {
        "weighted_only": sensitivity,
        "deployment_mandatory": mandatory_plan,
        "mandatory_plan_uncovered": mandatory_matrix.loc[
            ~mandatory_matrix.planned_coverage, "requirement_id"
        ].tolist(),
    }
    return result, matrix, pd.DataFrame(rows), sensitivity


def plot_study(frontier):
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    for policy, group in frontier.groupby("policy"):
        ax.step(group.budget_h, group.covered_weight, where="post", label=policy)
        ax.scatter(group.budget_h, group.covered_weight)
    ax.legend()
    ax.text(0.02, 0.95, "Mandatory plan infeasible below 2 h", transform=ax.transAxes, va="top")
    ax.set(
        xlabel="Assumed lab-hours budget",
        ylabel="Covered priority weight (not probability)",
        title="Synthetic proposed test coverage — no qualification evidence",
        ylim=(0, 11),
    )
    return fig


if __name__ == "__main__":
    result, matrix, frontier, sensitivity = study()
    print(result)
    print(matrix.to_string(index=False))
    print("Coverage-claim sensitivity:", sensitivity)
    plot_study(frontier)
    plt.show()
