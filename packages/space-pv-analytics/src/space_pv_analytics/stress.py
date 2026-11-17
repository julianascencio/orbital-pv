"""Four-arm combined-stressor interaction screening with sample-level resampling."""

import numpy as np
import pandas as pd

ARMS = ("control", "radiation", "thermal", "combined")


def combined_stress_interaction(
    samples: pd.DataFrame, *, bootstrap_samples: int = 4000, confidence: float = 0.95, seed: int = 0
):
    """Compare combined retention with a control-adjusted multiplicative baseline.

    Require unique independent sample_id, one campaign_id, arm, before_power_w
    and after_power_w. Each arm needs >=3 independent hardware samples, not
    repeated measurements of one device. Pmax conditions/boundaries must match.
    Caller must ensure randomized comparable hardware and matched stress levels.

    Let m be arm mean log(after/before). Interaction is
    m_combined - m_radiation - m_thermal + m_control. Its exponential is the
    combined-to-independent retention ratio (<1 indicates extra combined loss).
    Bootstrap whole before/after pairs within each arm; percentile bounds are
    approximate empirical uncertainty, not qualification or a causal guarantee.
    No dose/lifetime extrapolation or stress-order equivalence is assumed.
    """
    required = {"sample_id", "campaign_id", "arm", "before_power_w", "after_power_w"}
    if not required.issubset(samples.columns) or samples.empty:
        raise ValueError("Nonempty sample registry with required columns needed")
    if samples.sample_id.isna().any() or samples.sample_id.duplicated().any():
        raise ValueError("sample_id must identify unique independent hardware")
    if samples.campaign_id.isna().any() or samples.campaign_id.nunique() != 1:
        raise ValueError("One nonmissing campaign_id required")
    if samples.arm.isna().any() or set(samples.arm) != set(ARMS):
        raise ValueError("Require exactly control, radiation, thermal and combined arms")
    values = samples[["before_power_w", "after_power_w"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("Power must be finite and positive")
    if (
        isinstance(bootstrap_samples, bool)
        or not isinstance(bootstrap_samples, int)
        or not 100 <= bootstrap_samples <= 100_000
    ):
        raise ValueError("bootstrap_samples must be an integer in [100,100000]")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not np.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must be in (0,1)")
    data = samples.assign(log_retention=np.log(values[:, 1]) - np.log(values[:, 0]))
    groups = [data.loc[data.arm == arm, "log_retention"].to_numpy() for arm in ARMS]
    if min(map(len, groups)) < 3:
        raise ValueError("At least three independent samples per arm required")
    means = np.array([group.mean() for group in groups])
    signs = np.array([1, -1, -1, 1])
    rng = np.random.default_rng(seed)
    draws = np.zeros(bootstrap_samples)
    # Bounded memory: resample one arm/replicate at a time, preserving pairs.
    for group, sign in zip(groups, signs, strict=True):
        for i in range(bootstrap_samples):
            draws[i] += sign * rng.choice(group, size=len(group), replace=True).mean()
    low, high = np.quantile(draws, [(1 - confidence) / 2, (1 + confidence) / 2])
    independent_log = means[1] + means[2] - means[0]
    with np.errstate(over="ignore"):
        outputs = np.exp([independent_log, means[3], means @ signs, low, high])
    if not np.isfinite(outputs).all() or np.any(outputs == 0):
        raise ValueError("Retention outside representable numerical range")
    result = dict(
        zip(
            (
                "independent_retention",
                "combined_retention",
                "interaction_ratio",
                "ratio_lower",
                "ratio_upper",
            ),
            map(float, outputs),
            strict=True,
        )
    )
    result.update(
        confidence=confidence,
        bootstrap_samples=bootstrap_samples,
        seed=seed,
        extra_loss_supported=bool(high < -1e-12),
    )
    arms = pd.DataFrame(
        {"arm": ARMS, "samples": [len(g) for g in groups], "geometric_retention": np.exp(means)}
    )
    return result, arms
