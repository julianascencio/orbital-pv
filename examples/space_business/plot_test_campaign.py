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

from orbitalpv.campaign import plan_test_campaign
from orbitalpv.data import load_table


def study():
    root = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    req, tests, edges = [
        load_table(root / "_data" / f"campaign_{name}.csv")
        for name in ("requirements", "tests", "coverage")
    ]
    rows = []
    for budget in range(11):
        result, _ = plan_test_campaign(req, tests, edges, budget_h=budget)
        rows.append(result)
    result, matrix = plan_test_campaign(req, tests, edges, budget_h=8)
    # Sensitivity: withdraw a coverage claim; never silently assume equivalence.
    reduced = edges[~((edges.test_id == "combined-rt") & (edges.requirement_id == "thermal"))]
    sensitivity, _ = plan_test_campaign(req, tests, reduced, budget_h=8)
    return result, matrix, pd.DataFrame(rows), sensitivity


def plot_study(frontier):
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.step(frontier.budget_h, frontier.covered_weight, where="post")
    ax.scatter(frontier.budget_h, frontier.covered_weight)
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
