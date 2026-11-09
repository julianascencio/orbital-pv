"""Binomial deployment evidence under independent, exchangeable one-shot trials.

Statistical evidence is not certification or a substitute for physics-based
qualification. Repeated cycles on one unit are not independent hardware trials.
"""

from __future__ import annotations

import math
import operator

import pandas as pd


def _count(value: int, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a nonnegative integer")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a nonnegative integer") from exc
    if result < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return result


def _probability(value: float, name: str) -> None:
    if not math.isfinite(value) or not 0 < value < 1:
        raise ValueError(f"{name} must lie strictly between zero and one")


def _failure_cdf(n: int, failures: int, reliability: float) -> float:
    # Binomial lower tail in log space; only called with 0 < reliability < 1.
    terms = [
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log1p(-reliability)
        + (n - k) * math.log(reliability)
        for k in range(failures + 1)
    ]
    maximum = max(terms)
    return math.exp(maximum) * math.fsum(math.exp(x - maximum) for x in terms)


def deployment_reliability_lower_bound(
    successes: int, failures: int, *, confidence: float = 0.95
) -> float:
    """Exact one-sided Clopper-Pearson lower bound on per-unit success probability.

    Solve P(F <= observed_failures | R=lower) = 1-confidence for n trials.
    All-success bound is (1-confidence)**(1/n). All-failure bound is zero.
    Confidence describes repeated-sampling coverage, not a posterior probability.
    Counts must be independently justified; no pooling across design/protocols.
    """
    s, f = _count(successes, "successes"), _count(failures, "failures")
    _probability(confidence, "confidence")
    n = s + f
    if n == 0:
        raise ValueError("At least one completed trial is required")
    if s == 0:
        return 0.0
    if f == 0:
        return math.exp(math.log1p(-confidence) / n)
    low, high = 0.0, 1.0
    for _ in range(80):
        mid = (low + high) / 2
        if _failure_cdf(n, f, mid) < 1 - confidence:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def zero_failure_sample_size(reliability: float, *, confidence: float = 0.95) -> int:
    """Smallest fixed campaign with zero failures supporting the requested bound.

    n = ceil(log(1-confidence)/log(reliability)). This is not a sequential
    stopping rule. No number of repetitions proves unmodeled common-cause risks.
    """
    _probability(reliability, "reliability")
    _probability(confidence, "confidence")
    n = math.ceil(math.log1p(-confidence) / math.log(reliability))
    # Correct floating-point rounding at exact integer boundaries.
    while (
        n > 1 and deployment_reliability_lower_bound(n - 1, 0, confidence=confidence) >= reliability
    ):
        n -= 1
    while deployment_reliability_lower_bound(n, 0, confidence=confidence) < reliability:
        n += 1
    return n


def summarize_deployment_trials(frame: pd.DataFrame, *, confidence: float = 0.95) -> pd.DataFrame:
    """Screen a one-shot trial registry by design and protocol, without pooling.

    Columns: unit_id, design_id, protocol_id (nonempty strings), success (0/1).
    Duplicate unit IDs within a design/protocol fail even if outcomes agree.
    Unique IDs cannot establish physical independence: the caller must establish
    representative hardware, comparable stress exposure and absence of shared
    failure causes. Incomplete/censored records must not be encoded as successes.
    """
    required = {"unit_id", "design_id", "protocol_id", "success"}
    _probability(confidence, "confidence")
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("Provide a nonempty registry with unit/design/protocol/success columns")
    ids = ["design_id", "protocol_id", "unit_id"]
    for column in ids:
        if not frame[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError("Identifiers must be nonempty strings")
    if frame.duplicated(ids).any():
        raise ValueError("Repeated hardware within a protocol cannot count as independent trials")
    if not frame.success.isin([0, 1]).all():
        raise ValueError("success must contain only completed binary outcomes 0/1")
    rows = []
    for _, group in frame.groupby(["design_id", "protocol_id"], sort=True):
        design = str(group["design_id"].iloc[0])
        protocol = str(group["protocol_id"].iloc[0])
        successes = int(group.success.sum())
        failures = len(group) - successes
        rows.append(
            {
                "design_id": design,
                "protocol_id": protocol,
                "units": len(group),
                "successes": successes,
                "failures": failures,
                "confidence": confidence,
                "reliability_lower": deployment_reliability_lower_bound(
                    successes, failures, confidence=confidence
                ),
            }
        )
    return pd.DataFrame(rows)
